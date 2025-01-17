from typing import Dict, List, Literal, Optional, Tuple

from rest_framework.exceptions import ValidationError

from ee.clickhouse.client import sync_execute
from ee.clickhouse.queries.funnels.funnel_persons import ClickhouseFunnelPersons
from ee.clickhouse.queries.paths.path_event_query import PathEventQuery
from ee.clickhouse.sql.paths.path import PATH_ARRAY_QUERY
from posthog.models import Filter, Team
from posthog.models.filters.path_filter import PathFilter

EVENT_IN_SESSION_LIMIT_DEFAULT = 5
SESSION_TIME_THRESHOLD_DEFAULT = 1800000  # milliseconds to 30 minutes


class ClickhousePathsNew:
    _filter: PathFilter
    _funnel_filter: Optional[Filter]
    _team: Team

    def __init__(self, filter: PathFilter, team: Team, funnel_filter: Optional[Filter] = None) -> None:
        self._filter = filter
        self._team = team
        self.params = {
            "team_id": self._team.pk,
            "events": [],  # purely a speed optimization, don't need this for filtering
            "event_in_session_limit": self._filter.step_limit or EVENT_IN_SESSION_LIMIT_DEFAULT,
            "session_time_threshold": SESSION_TIME_THRESHOLD_DEFAULT,
            "autocapture_match": "%autocapture:%",
        }
        self._funnel_filter = funnel_filter

        if self._filter.include_all_custom_events and self._filter.custom_events:
            raise ValidationError("Cannot include all custom events and specific custom events in the same query")

        # TODO: don't allow including $pageview and excluding $pageview at the same time
        # TODO: Filter on specific autocapture / page URLs

    def run(self, *args, **kwargs):

        results = self._exec_query()
        return self._format_results(results)

    def _format_results(self, results):
        if not results or len(results) == 0:
            return []

        resp = []
        for res in results:
            resp.append({"source": res[0], "target": res[1], "value": res[2], "average_conversion_time": res[3]})
        return resp

    def _exec_query(self) -> List[Tuple]:
        query = self.get_query()
        return sync_execute(query, self.params)

    def get_query(self) -> str:

        if self._filter.funnel_paths and self._funnel_filter:
            return self.get_path_query_by_funnel(funnel_filter=self._funnel_filter)
        else:
            return self.get_path_query()

    def get_path_query(self) -> str:
        path_event_query, params = PathEventQuery(filter=self._filter, team_id=self._team.pk).get_query()
        self.params.update(params)

        boundary_event_filter, start_params = (
            self.get_end_point_filter() if self._filter.end_point else self.get_start_point_filter()
        )
        path_limiting_clause, time_limiting_clause = self.get_filtered_path_ordering()
        compacting_function = self.get_array_compacting_function()
        self.params.update(start_params)
        return PATH_ARRAY_QUERY.format(
            path_event_query=path_event_query,
            boundary_event_filter=boundary_event_filter,
            path_limiting_clause=path_limiting_clause,
            time_limiting_clause=time_limiting_clause,
            compacting_function=compacting_function,
        )

    def get_path_query_by_funnel(self, funnel_filter: Filter):
        path_query = self.get_path_query()
        funnel_persons_generator = ClickhouseFunnelPersons(funnel_filter, self._team)
        funnel_persons_query = funnel_persons_generator.get_query()
        funnel_persons_query_new_params = funnel_persons_query.replace("%(", "%(funnel_")
        funnel_persons_param = funnel_persons_generator.params
        new_funnel_params = {"funnel_" + str(key): val for key, val in funnel_persons_param.items()}
        self.params.update(new_funnel_params)
        return f"""
        WITH {PathEventQuery.FUNNEL_PERSONS_ALIAS} AS (
            {funnel_persons_query_new_params}
        )
        {path_query}
        """

    def get_start_point_filter(self) -> Tuple[str, Dict]:

        if not self._filter.start_point:
            return "", {"target_point": None}

        return "WHERE arrayElement(limited_path, 1) = %(target_point)s", {"target_point": self._filter.start_point}

    def get_end_point_filter(self) -> Tuple[str, Dict]:
        if not self._filter.end_point:
            return "", {"target_point": None}

        return "WHERE arrayElement(limited_path, -1) = %(target_point)s", {"target_point": self._filter.end_point}

    def get_array_compacting_function(self) -> Literal["arrayResize", "arraySlice"]:
        if self._filter.end_point:
            return "arrayResize"
        else:
            return "arraySlice"

    def get_filtered_path_ordering(self) -> Tuple[str, str]:

        if self._filter.end_point:
            return (
                "arraySlice(filtered_path, (-1) * %(event_in_session_limit)s)",
                "arraySlice(filtered_timings, (-1) * %(event_in_session_limit)s)",
            )
        else:
            return (
                "arraySlice(filtered_path, 1, %(event_in_session_limit)s)",
                "arraySlice(filtered_timings, 1, %(event_in_session_limit)s)",
            )
