"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

export default function SeriesChart({ seriesName, meetingDate }: { seriesName: string; meetingDate: string }) {
  const [data, setData] = useState<{ date: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/v1/series/${encodeURIComponent(seriesName)}/observations?meeting_date=${meetingDate}`);
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (e) {
        console.error("Failed to fetch chart data", e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [seriesName, meetingDate]);

  if (loading) return <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#666", fontSize: 12 }}>Loading chart...</div>;
  if (data.length === 0) return <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#666", fontSize: 12 }}>No historical data found</div>;

  // Find min and max for better Y axis scaling
  const values = data.map(d => d.value).filter(v => v !== null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = (max - min) * 0.1 || 1;

  return (
    <div style={{ width: "100%", height: 250, marginTop: 16 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
          <XAxis 
            dataKey="date" 
            tick={{ fontSize: 10, fill: "#666" }} 
            axisLine={{ stroke: "#333" }} 
            tickLine={{ stroke: "#333" }} 
            minTickGap={30}
          />
          <YAxis 
            domain={[min - padding, max + padding]} 
            tick={{ fontSize: 10, fill: "#666" }} 
            axisLine={{ stroke: "#333" }} 
            tickLine={{ stroke: "#333" }} 
            tickFormatter={(val) => val.toFixed(1)}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: "#121212", border: "1px solid #333", fontSize: 12, color: "#ccc" }} 
            itemStyle={{ color: "var(--green)" }}
            labelStyle={{ color: "#888", marginBottom: 4 }}
          />
          <ReferenceLine 
            x={meetingDate} 
            stroke="var(--red)" 
            strokeDasharray="3 3" 
            label={{ position: 'insideTopLeft', value: 'FOMC MEETING', fill: 'var(--red)', fontSize: 10, fontWeight: 700 }}
          />
          <Line 
            type="monotone" 
            dataKey="value" 
            stroke="var(--green)" 
            strokeWidth={2} 
            dot={{ r: 2, fill: "var(--green)", strokeWidth: 0 }} 
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
