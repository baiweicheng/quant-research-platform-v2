import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Period, Run } from "./types";
import { percent, shortDate } from "./api";

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  CanvasRenderer,
]);

export default function PerformanceChart({
  run,
  period,
}: {
  run: Run;
  period: Period;
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = echarts.init(element.current);
    const rows = run.curve.slice(run.windows[period].start_index);
    const base = Number(rows[0]?.equity);
    const spyBase = Number(rows[0]?.benchmark);
    const series = [
      {
        name: run.strategy.name,
        data: rows.map((row) => (Number(row.equity) / base - 1) * 100),
        type: "line" as const,
        showSymbol: false,
        lineStyle: { width: 2.5, color: "#22775f" },
        itemStyle: { color: "#22775f" },
        areaStyle: { color: "#22775f", opacity: 0.05 },
      },
    ];
    if (rows.every((row) => row.benchmark !== null))
      series.push({
        name: "SPY",
        data: rows.map((row) => (Number(row.benchmark) / spyBase - 1) * 100),
        type: "line",
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#98a5a0" },
        itemStyle: { color: "#98a5a0" },
        areaStyle: { color: "#98a5a0", opacity: 0 },
      });
    chart.setOption({
      textStyle: { fontSize: 14 },
      animation: false,
      aria: {
        enabled: true,
        label: {
          description: `Backtest performance for ${run.strategy.name}. Return ${percent(run.windows[period].metrics.return)}. Data is also summarized above the chart.`,
        },
      },
      grid: { left: 12, right: 28, top: 20, bottom: 36, containLabel: true },
      tooltip: {
        trigger: "axis",
        textStyle: { fontSize: 14 },
        valueFormatter: (value: unknown) => `${Number(value).toFixed(2)}%`,
      },
      xAxis: {
        type: "category",
        data: rows.map((row) => row.session),
        boundaryGap: false,
        axisLabel: {
          fontSize: 14,
          hideOverlap: true,
          color: "#718078",
          formatter: (value: string) => shortDate(value).replace(/, \d{4}/, ""),
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        position: "right",
        axisLabel: { formatter: "{value}%", color: "#718078", fontSize: 14 },
        splitLine: { lineStyle: { color: "#edf1ee" } },
      },
      series,
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [run, period]);
  return (
    <div
      className="chart"
      ref={element}
      role="img"
      aria-label={`${run.strategy.name} backtest performance${run.windows[period].metrics.benchmark_return === null ? "" : " compared with SPY"}; statistics above chart`}
    />
  );
}
