import {
  ResponsiveContainer,
  LineChart,
  AreaChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { cn } from '@/lib/utils';
import type { MetricSeries } from '@/types';

interface MetricsChartProps {
  data: MetricSeries[];
  type?: 'line' | 'area';
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
  className?: string;
}

export function MetricsChart({
  data,
  type = 'line',
  height = 300,
  showLegend = false,
  showGrid = true,
  className,
}: MetricsChartProps) {
  // Merge all series data by timestamp
  const mergedData = data[0]?.data.map((point, index) => {
    const merged: Record<string, unknown> = { timestamp: point.timestamp };
    data.forEach((series) => {
      merged[series.name] = series.data[index]?.value ?? 0;
    });
    return merged;
  }) ?? [];

  const ChartComponent = type === 'area' ? AreaChart : LineChart;
  const DataComponent = type === 'area' ? Area : Line;

  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ChartComponent data={mergedData}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#44403c"
              opacity={0.3}
            />
          )}
          <XAxis
            dataKey="timestamp"
            tickFormatter={(t) =>
              new Date(t).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })
            }
            stroke="#78716c"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="#78716c"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1c1917',
              border: '1px solid #44403c',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#fafaf9',
            }}
            labelFormatter={(t) => new Date(t as string).toLocaleString()}
            formatter={(value) => [
              typeof value === 'number' ? value.toFixed(2) : value,
              undefined,
            ]}
          />
          {showLegend && <Legend />}
          {data.map((series) =>
            type === 'area' ? (
              <Area
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={series.color || '#3b82f6'}
                fill={series.color || '#3b82f6'}
                fillOpacity={0.2}
                strokeWidth={2}
              />
            ) : (
              <Line
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={series.color || '#3b82f6'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            )
          )}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  );
}

export default MetricsChart;
