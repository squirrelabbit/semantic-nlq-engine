import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar
} from 'recharts';
import { Box, Typography, Paper, Grid, Stack, Chip } from '@mui/material';
import { BarChart as BarChartIcon } from '@mui/icons-material';

interface ChartRendererProps {
  rows: Record<string, any>[];
  plan?: any;
}

// A new component to display single values prominently
const humanizeKey = (key: string) => {
  const mapping: Record<string, string> = {
    h_pop: '주거 인구',
    w_pop: '직장 인구',
    v_pop: '방문 인구',
    total_h_pop: '주거 인구',
    total_w_pop: '직장 인구',
    total_v_pop: '방문 인구',
  };
  return mapping[key] || key.replace(/_/g, ' ').toUpperCase();
};

const formatNumber = (value: any) => {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString();
};

const SingleValueDisplay: React.FC<{ rows: Record<string, any>[] }> = ({ rows }) => {
  if (!rows || rows.length === 0) return null;

  const firstRow = rows[0];
  const dataEntries = Object.entries(firstRow).filter(([, value]) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return !Number.isNaN(num);
  });
  const total = dataEntries.reduce((acc, [, value]) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return acc + (Number.isNaN(num) ? 0 : num);
  }, 0);

  return (
    <Stack spacing={2} sx={{ height: '100%' }}>
      <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', border: '1px solid', borderColor: 'grey.200' }}>
        <Typography variant="caption" color="text.secondary">총합</Typography>
        <Typography variant="h4" fontWeight="bold" color="primary">
          {formatNumber(total)}명
        </Typography>
      </Paper>
      <Grid container spacing={2}>
        {dataEntries.map(([key, value], index) => {
          const num = typeof value === 'number' ? value : parseFloat(value);
          const share = total > 0 ? (num / total) * 100 : 0;
          return (
            <Grid item key={key} xs={12} sm={4}>
              <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'grey.200' }}>
                <Typography variant="overline" color="text.secondary">
                  {humanizeKey(key)}
                </Typography>
                <Typography variant="h5" fontWeight="bold">
                  {formatNumber(value)}명
                </Typography>
                <Chip
                  size="small"
                  label={`${share.toFixed(1)}%`}
                  sx={{ mt: 1, bgcolor: `hsl(${index * 90}, 70%, 92%)`, color: 'text.secondary' }}
                />
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Stack>
  );
};


const ChartRenderer: React.FC<ChartRendererProps> = ({ rows, plan }) => {
  if (!rows || rows.length === 0) {
    return (
      <Box textAlign="center" p={4}>
        <BarChartIcon sx={{ fontSize: 60, color: 'grey.300', mb: 2 }} />
        <Typography variant="body1" color="text.secondary">시각화할 데이터가 없습니다.</Typography>
      </Box>
    );
  }

  // Determine chart type: explicitly from plan, or guess as a fallback
  const explicitChartType = plan?.visualization_type;

  const dataKeys = Object.keys(rows[0]);
  const chartData = rows.map(row => {
    const newRow: Record<string, any> = {};
    for (const key of dataKeys) {
      newRow[key] = typeof row[key] === 'number' ? row[key] : (parseFloat(row[key]) || row[key]);
    }
    return newRow;
  });

  const getChartType = () => {
    if (explicitChartType) return explicitChartType;

    // Fallback heuristic logic from the original component
    const timeKeys = dataKeys.filter(key => key.includes('std_ymd') || key.includes('std_ym') || key.includes('date'));
    if (timeKeys.length > 0) {
      const numericKeys = dataKeys.filter(key => key !== timeKeys[0] && typeof rows[0][key] === 'number');
      if (numericKeys.length > 0) return 'line';
    }

    const categoricalKeys = dataKeys.filter(key => typeof rows[0][key] === 'string');
    const numericKeys = dataKeys.filter(key => typeof rows[0][key] === 'number');
    if (categoricalKeys.length > 0 && numericKeys.length > 0) return 'bar';

    return 'table'; // Default fallback
  };

  const chartType = getChartType();
  const chartTitle = plan?.original_question || "분석 결과";
  
  const renderChart = () => {
    const xAxisKey = dataKeys.find(key => typeof chartData[0][key] === 'string' || key.includes('std_ymd'));
    const valueKeys = dataKeys.filter(key => typeof chartData[0][key] === 'number');

    switch (chartType) {
      case 'single_value':
        return <SingleValueDisplay rows={rows} />;
      
      case 'line':
        if (!xAxisKey || valueKeys.length === 0) return null;
        return (
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xAxisKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            {valueKeys.map((key, index) => (
              <Line key={key} type="monotone" dataKey={key} stroke={`hsl(${index * 100}, 70%, 50%)`} activeDot={{ r: 8 }} />
            ))}
          </LineChart>
        );
        
      case 'bar':
        if (!xAxisKey || valueKeys.length === 0) return null;
        return (
          <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xAxisKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            {valueKeys.map((key, index) => (
              <Bar key={key} dataKey={key} fill={`hsl(${index * 100}, 70%, 50%)`} />
            ))}
          </BarChart>
        );

      default:
        return (
          <Box textAlign="center" p={4}>
            <BarChartIcon sx={{ fontSize: 60, color: 'grey.300', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">시각화 유형을 결정할 수 없습니다.</Typography>
            <Typography variant="caption" color="text.disabled">(데이터: {JSON.stringify(rows[0])})</Typography>
          </Box>
        );
    }
  };

  return (
    <Paper elevation={1} sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column', bgcolor: 'white' }}>
      <Typography variant="h6" gutterBottom textAlign="center">{chartTitle}</Typography>
      <ResponsiveContainer width="100%" height={400}>
        {renderChart()}
      </ResponsiveContainer>
    </Paper>
  );
};

export default ChartRenderer;
