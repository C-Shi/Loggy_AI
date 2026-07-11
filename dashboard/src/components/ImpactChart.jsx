import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import { normalizeImpact } from "../lib/format.js";

/**
 * Bar chart of total incident_count grouped by report.business_impact.
 */
export default function ImpactChart({ reports }) {
  const ref = useRef(null);

  const data = useMemo(() => {
    const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
    const counts = d3.rollup(
      reports,
      (v) => d3.sum(v, (d) => Number(d.incident_count) || 1),
      (d) => normalizeImpact(d.business_impact)
    );
    return order.map((impact) => ({
      impact,
      count: counts.get(impact) || 0,
    }));
  }, [reports]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.innerHTML = "";

    const width = el.clientWidth || 640;
    const height = 260;
    const margin = { top: 20, right: 20, bottom: 40, left: 48 };

    const svg = d3
      .select(el)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("role", "img")
      .attr("aria-label", "Incidents by business_impact");

    const x = d3
      .scaleBand()
      .domain(data.map((d) => d.impact))
      .range([margin.left, width - margin.right])
      .padding(0.35);

    const y = d3
      .scaleLinear()
      .domain([0, Math.max(d3.max(data, (d) => d.count) || 0, 1)])
      .nice()
      .range([height - margin.bottom, margin.top]);

    const color = {
      CRITICAL: "#c53030",
      HIGH: "#dd6b20",
      MEDIUM: "#d69e2e",
      LOW: "#2f855a",
    };

    svg
      .append("g")
      .attr("class", "grid")
      .attr("transform", `translate(${margin.left},0)`)
      .call(
        d3
          .axisLeft(y)
          .ticks(4)
          .tickSize(-(width - margin.left - margin.right))
          .tickFormat("")
      )
      .selectAll("line")
      .attr("stroke", "#e2e8f0")
      .attr("stroke-dasharray", "3,3");

    svg.select(".grid").select(".domain").remove();

    svg
      .append("g")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x))
      .call((g) => g.select(".domain").attr("stroke", "#cbd5e0"))
      .selectAll("text")
      .attr("font-size", 12)
      .attr("fill", "#4a5568")
      .attr("font-weight", 600);

    svg
      .append("g")
      .attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(4))
      .call((g) => g.select(".domain").attr("stroke", "#cbd5e0"))
      .selectAll("text")
      .attr("font-size", 11)
      .attr("fill", "#718096");

    svg
      .selectAll(".bar")
      .data(data)
      .join("rect")
      .attr("class", "bar")
      .attr("x", (d) => x(d.impact))
      .attr("y", (d) => y(d.count))
      .attr("width", x.bandwidth())
      .attr("height", (d) => Math.max(0, y(0) - y(d.count)))
      .attr("fill", (d) => color[d.impact])
      .attr("rx", 4);

    svg
      .selectAll(".bar-label")
      .data(data.filter((d) => d.count > 0))
      .join("text")
      .attr("class", "bar-label")
      .attr("x", (d) => x(d.impact) + x.bandwidth() / 2)
      .attr("y", (d) => y(d.count) - 6)
      .attr("text-anchor", "middle")
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .attr("fill", "#2d3748")
      .text((d) => d.count);
  }, [data]);

  return <div className="chart-wrap" ref={ref} />;
}
