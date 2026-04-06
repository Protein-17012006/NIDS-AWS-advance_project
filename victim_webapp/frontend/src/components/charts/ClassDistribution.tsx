import React, { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import { PredictResponse, CLASS_COLORS } from '../../types';

interface Props {
  data: PredictResponse;
}

const ClassDistribution: React.FC<Props> = ({ data }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 600;
    const height = 400;
    const margin = { top: 30, right: 120, bottom: 60, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Compute class distribution from predictions vs true labels
    const { class_names, predictions, true_labels } = data;
    const trueDistrib = class_names.map((_, i) => true_labels.filter(l => l === i).length);
    const predDistrib = class_names.map((_, i) => predictions.filter(p => p === i).length);

    const allGroups = class_names;
    const maxVal = Math.max(...trueDistrib, ...predDistrib);

    // Scales
    const x0 = d3.scaleBand().domain(allGroups).range([0, innerW]).paddingInner(0.2).paddingOuter(0.1);
    const x1 = d3.scaleBand().domain(['True', 'Predicted']).range([0, x0.bandwidth()]).padding(0.05);
    const y = d3.scaleLinear().domain([0, maxVal * 1.1]).range([innerH, 0]);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x0))
      .selectAll('text')
      .attr('fill', '#cbd5e1')
      .attr('font-size', '11px');

    g.append('g')
      .call(d3.axisLeft(y).ticks(6))
      .selectAll('text')
      .attr('fill', '#94a3b8')
      .attr('font-size', '11px');

    // Grid
    g.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(y).ticks(6).tickSize(-innerW).tickFormat(() => ''))
      .selectAll('line')
      .attr('stroke', 'rgba(71,85,105,0.3)');
    g.select('.grid .domain').remove();

    // Axis labels
    g.append('text')
      .attr('x', innerW / 2).attr('y', innerH + 45)
      .attr('text-anchor', 'middle').attr('fill', '#94a3b8')
      .attr('font-size', '13px').text('Attack Class');
    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerH / 2).attr('y', -45)
      .attr('text-anchor', 'middle').attr('fill', '#94a3b8')
      .attr('font-size', '13px').text('Sample Count');

    // Bars — True
    g.selectAll('.bar-true')
      .data(allGroups)
      .enter().append('rect')
      .attr('class', 'bar-true')
      .attr('x', (d) => (x0(d) || 0) + (x1('True') || 0))
      .attr('width', x1.bandwidth())
      .attr('y', innerH)
      .attr('height', 0)
      .attr('rx', 3)
      .attr('fill', (d) => CLASS_COLORS[d] || '#64748b')
      .attr('opacity', 0.7)
      .transition().duration(800).ease(d3.easeCubicOut)
      .attr('y', (_, i) => y(trueDistrib[i]))
      .attr('height', (_, i) => innerH - y(trueDistrib[i]));

    // Bars — Predicted
    g.selectAll('.bar-pred')
      .data(allGroups)
      .enter().append('rect')
      .attr('class', 'bar-pred')
      .attr('x', (d) => (x0(d) || 0) + (x1('Predicted') || 0))
      .attr('width', x1.bandwidth())
      .attr('y', innerH)
      .attr('height', 0)
      .attr('rx', 3)
      .attr('fill', (d) => CLASS_COLORS[d] || '#64748b')
      .attr('opacity', 1)
      .attr('stroke', '#fff')
      .attr('stroke-width', 1)
      .transition().duration(800).delay(200).ease(d3.easeCubicOut)
      .attr('y', (_, i) => y(predDistrib[i]))
      .attr('height', (_, i) => innerH - y(predDistrib[i]));

    // Tooltips
    const tooltip = d3.select(svgRef.current.parentElement!)
      .append('div')
      .style('position', 'absolute')
      .style('background', '#1e293b')
      .style('border', '1px solid #475569')
      .style('border-radius', '8px')
      .style('padding', '8px 12px')
      .style('color', '#e2e8f0')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0);

    g.selectAll('rect')
      .on('mouseover', function (event: MouseEvent, d: any) {
        const idx = allGroups.indexOf(d);
        const isTrue = (this as Element).classList.contains('bar-true');
        const val = isTrue ? trueDistrib[idx] : predDistrib[idx];
        tooltip.style('opacity', 1)
          .html(`<strong>${d}</strong><br/>${isTrue ? 'True' : 'Predicted'}: ${val}`);
        d3.select(this).attr('opacity', 1).attr('stroke-width', 2);
      })
      .on('mousemove', (event: MouseEvent) => {
        tooltip.style('left', `${event.offsetX + 15}px`).style('top', `${event.offsetY - 10}px`);
      })
      .on('mouseout', function () {
        tooltip.style('opacity', 0);
        d3.select(this)
          .attr('opacity', (this as Element).classList.contains('bar-true') ? 0.7 : 1)
          .attr('stroke-width', (this as Element).classList.contains('bar-pred') ? 1 : 0);
      });

    // Legend
    const legend = g.append('g').attr('transform', `translate(${innerW + 10}, 0)`);
    [{ label: 'True', opacity: 0.7 }, { label: 'Predicted', opacity: 1 }].forEach((item, i) => {
      const row = legend.append('g').attr('transform', `translate(0, ${i * 24})`);
      row.append('rect').attr('width', 16).attr('height', 16)
        .attr('rx', 3).attr('fill', '#3b82f6').attr('opacity', item.opacity);
      row.append('text').attr('x', 22).attr('y', 13)
        .attr('fill', '#cbd5e1').attr('font-size', '12px').text(item.label);
    });

    return () => { tooltip.remove(); };
  }, [data]);

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: '16px', border: '1px solid #334155', position: 'relative' }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>
        Class Distribution: True vs Predicted (D3.js)
      </h3>
      <svg ref={svgRef} style={{ width: '100%', height: 400 }} />
    </div>
  );
};

export default ClassDistribution;
