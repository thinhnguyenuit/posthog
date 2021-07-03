import React, { useEffect } from 'react'
import { List } from 'antd'
import VirtualizedList from 'react-virtualized/dist/commonjs/List'
import { InfiniteLoader, ListRowProps, ListRowRenderer, AutoSizer } from 'react-virtualized'
import { PropertyKeyInfo } from 'lib/components/PropertyKeyInfo'
import { useThrottledCallback } from 'use-debounce/lib'
import { Loading } from 'lib/utils'
import { useActions, useValues } from 'kea'
import { infiniteListLogic } from 'lib/components/PropertyFilters/infiniteListLogic'

interface InfiniteListProps {
    pageKey: string
    type: string
    endpoint: string
    searchQuery?: string
    onSelect: (type: string, id: string | number, name: string) => void
    selectedItemKey: string | number | null
}

export function InfiniteList({
    pageKey,
    type,
    endpoint,
    searchQuery,
    onSelect,
    selectedItemKey,
}: InfiniteListProps): JSX.Element {
    const logic = infiniteListLogic({ pageKey, type, endpoint })
    const { results, itemsLoading, totalCount } = useValues(logic)
    const { loadItems } = useActions(logic)

    const renderItem: ListRowRenderer = ({ index, style }: ListRowProps): JSX.Element | null => {
        const item = results[index]
        return item ? (
            <List.Item
                className={selectedItemKey === item.id ? 'selected' : undefined}
                key={item.id}
                onClick={() => onSelect(type, item.id, item.name)}
                style={style}
                data-attr={`prop-filter-${type}-${index}`}
            >
                <PropertyKeyInfo value={item.name} />
            </List.Item>
        ) : null
    }

    useEffect(
        useThrottledCallback(() => {
            // TODO breakpoint in loadItems
            loadItems({ search: searchQuery })
        }, 100),
        [searchQuery]
    )

    return (
        <div style={{ minHeight: '200px' }}>
            {itemsLoading && <Loading />}
            <AutoSizer>
                {({ height, width }: { height: number; width: number }) => (
                    <InfiniteLoader
                        isRowLoaded={({ index }) => !!results[index]}
                        loadMoreRows={({ startIndex, stopIndex }) => {
                            // TODO async load and return Promise<results>
                            loadItems({ search: searchQuery, offset: startIndex, limit: stopIndex - startIndex })
                        }}
                        rowCount={totalCount || 0}
                    >
                        {({ onRowsRendered, registerChild }) => (
                            <VirtualizedList
                                height={height}
                                onRowsRendered={onRowsRendered}
                                ref={registerChild}
                                overscanRowCount={0}
                                rowCount={totalCount || 0}
                                rowHeight={35}
                                rowRenderer={renderItem}
                                width={width}
                                tabIndex={-1}
                            />
                        )}
                    </InfiniteLoader>
                )}
            </AutoSizer>
        </div>
    )
}
