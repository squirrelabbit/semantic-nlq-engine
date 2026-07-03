import React from 'react';
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  Chip,
  Grid,
  List,
  ListItem,
  ListItemText,
  Divider
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  Feed as FeedIcon,
  Schedule as ScheduleIcon,
  Tag as TagIcon,
  WarningAmber as WarningIcon
} from '@mui/icons-material';

interface ChangeItem {
  region: string;
  change_rate: number | null;
  diff: number | null;
}

interface DailyReport {
  title: string;
  date: string;
  summary: string;
  top_changes: {
    increase: ChangeItem[];
    decrease: ChangeItem[];
  };
  anomalies: {
    status: string;
    message: string;
    items: ChangeItem[];
  };
  context: {
    events: string[];
    note: string;
  };
  data_status: {
    std_ymd: string;
    admin_code_correction: boolean;
    pii_masking: boolean;
  };
}

const apiBaseUrl = import.meta.env?.VITE_API_BASE_URL ?? 'http://localhost:8000';

const fetchLatestReport = async (): Promise<DailyReport> => {
  const response = await fetch(`${apiBaseUrl}/api/report/latest`);
  if (!response.ok) {
    throw new Error('Failed to fetch daily report');
  }
  return response.json();
};

const DailyBriefing: React.FC = () => {
  const { data, isLoading, error } = useQuery<DailyReport, Error>({
    queryKey: ['dailyReportLatest'],
    queryFn: fetchLatestReport,
  });

  if (isLoading) return (
    <Box display="flex" justifyContent="center" alignItems="center" height="200px">
      <CircularProgress />
      <Typography variant="h6" sx={{ ml: 2 }}>Loading Daily Briefings...</Typography>
    </Box>
  );
  if (error) return (
    <Typography color="error">Error: {error.message}</Typography>
  );

  return (
    <Box>
      <Typography variant="h5" gutterBottom>데일리 브리핑</Typography>
      <Grid container spacing={3}>
        {data ? (
          <>
            <Grid item xs={12} md={7}>
              <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
                <Typography variant="subtitle1" fontWeight="bold">{data.title}</Typography>
                <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', color: 'text.secondary', fontSize: '0.75rem' }}>
                  <ScheduleIcon fontSize="inherit" sx={{ mr: 0.5 }} />
                  기준일: {data.date}
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  {data.summary}
                </Typography>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom>이상 징후 감지</Typography>
                {data.anomalies.status === 'none' ? (
                  <Typography variant="body2" color="text.secondary">{data.anomalies.message}</Typography>
                ) : (
                  <List dense>
                    {data.anomalies.items.map((item, index) => (
                      <ListItem key={index} disablePadding>
                        <ListItemText
                          primary={`${item.region} (${item.change_rate !== null ? `${(item.change_rate * 100).toFixed(1)}%` : '-'})`}
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Paper>
            </Grid>
            <Grid item xs={12} md={5}>
              <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom>주요 변화 지역</Typography>
                <Typography variant="caption" color="text.secondary">증가 상위 3개</Typography>
                <List dense>
                  {data.top_changes.increase.map((item, index) => (
                    <ListItem key={`inc-${index}`} disablePadding>
                      <ListItemText
                        primary={`${item.region}`}
                        secondary={`증감률: ${item.change_rate !== null ? `${(item.change_rate * 100).toFixed(1)}%` : '-'}`}
                      />
                    </ListItem>
                  ))}
                </List>
                <Typography variant="caption" color="text.secondary">감소 상위 3개</Typography>
                <List dense>
                  {data.top_changes.decrease.map((item, index) => (
                    <ListItem key={`dec-${index}`} disablePadding>
                      <ListItemText
                        primary={`${item.region}`}
                        secondary={`증감률: ${item.change_rate !== null ? `${(item.change_rate * 100).toFixed(1)}%` : '-'}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12}>
              <Paper elevation={1} sx={{ p: 3, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">참고 맥락</Typography>
                  <Typography variant="body2">
                    {data.context.events.length > 0 ? data.context.events.join(', ') : data.context.note}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">데이터 상태</Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                    <Chip size="small" icon={<TagIcon />} label={`기준일: ${data.data_status.std_ymd}`} />
                    <Chip
                      size="small"
                      icon={<WarningIcon fontSize="small" />}
                      label={`행정 코드 보정: ${data.data_status.admin_code_correction ? '적용' : '미적용'}`}
                    />
                    <Chip size="small" label={`PII 마스킹: ${data.data_status.pii_masking ? '적용' : '미적용'}`} />
                  </Box>
                </Box>
              </Paper>
            </Grid>
          </>
        ) : (
          <Grid item xs={12}>
            <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
              <FeedIcon sx={{ fontSize: 60, color: 'grey.300', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">아직 생성된 리포트가 없습니다.</Typography>
              <Typography variant="body2" color="text.disabled">
                `scripts/poc_daily_report.py` 실행 후 다시 확인하세요.
              </Typography>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default DailyBriefing;
