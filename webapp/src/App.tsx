import React, { useState, useEffect, useRef } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  CssBaseline,
  Divider,
  Container,
  Paper,
  FormControlLabel,
  Switch,
  TextField,
  InputAdornment,
  IconButton,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Tabs, // Import Tabs
  Tab, // Import Tab
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Chat as ChatIcon,
  Settings as SettingsIcon,
  Send as SendIcon,
  LightbulbOutlined as InsightIcon,
  CodeOutlined as CodeIcon,
  WarningAmberOutlined as WarningIcon,
  CheckCircleOutline as CheckCircleIcon,
  ExpandMore as ExpandMoreIcon,
  AccessTime as AccessTimeIcon,
  AccountCircle as AccountCircleIcon,
  BarChart as BarChartIcon,
  People as PeopleIcon,
  Description as DescriptionIcon, // For Semantic Metadata
  HistoryEdu as HistoryEduIcon // For Knowledge Cards
} from '@mui/icons-material';
import { useMutation } from '@tanstack/react-query';

// Import the new components
import SemanticMetadataTable from './components/SemanticMetadataTable';
import KnowledgeCardTable from './components/KnowledgeCardTable';
import ChartRenderer from './components/ChartRenderer';
import DailyBriefing from './components/DailyBriefing'; // Import DailyBriefing


const drawerWidth = 240;

interface MockScenario {
  id?: string;
  question?: string;
  text?: string;
  viz_type?: string;
  expected_shape?: string;
  data_ref?: string;
  planner_file?: string;
  coder_file?: string;
}

interface NlqRequest {
  question: string;
  two_stage?: boolean;
  execute?: boolean;
  interpret?: boolean;
  direct?: boolean;
  use_mock?: boolean;
  mock_data_ref?: string;
  mock_planner_file?: string;
  mock_coder_file?: string;
}

interface NlqResponse {
  plan: any;
  sql?: string;
  rows?: Record<string, any>[];
  insight?: any;
  request_id: string;
}

interface ChatMessage {
  role: 'user' | 'bot';
  content: string | NlqResponse | { error: string };
}

// A component to render the bot's structured response
const BotResponse: React.FC<{ response: NlqResponse | { error: string } }> = ({ response }) => {
  if ('error' in response) {
    return (
      <Card variant="outlined" sx={{ bgcolor: 'error.light', color: 'error.contrastText' }}>
        <CardContent>
          <Box display="flex" alignItems="center" gap={1}>
            <WarningIcon fontSize="small" />
            <Typography variant="body2" fontWeight="bold">오류:</Typography>
          </Box>
          <Typography variant="body2">{response.error}</Typography>
        </CardContent>
      </Card>
    );
  }

  const { sql, rows, insight } = response;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {insight && (
        <Card variant="outlined" sx={{ bgcolor: 'info.light' }}>
          <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
            <Box display="flex" alignItems="center" gap={1}>
              <InsightIcon fontSize="small" color="info" />
              <Typography variant="body2" fontWeight="bold" color="info.main">분석 요약</Typography>
            </Box>
            <Typography variant="body2" sx={{ mt: 0.5 }}>{insight.summary || JSON.stringify(insight)}</Typography>
          </CardContent>
        </Card>
      )}
      {sql && (
        <Accordion sx={{ bgcolor: 'grey.100' }} elevation={0}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <CodeIcon fontSize="small" sx={{ mr: 1, color: 'grey.600' }} />
            <Typography variant="caption" sx={{ color: 'grey.800' }}>SQL 보기</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ bgcolor: 'grey.900', color: 'common.white', p: 1 }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.6rem' }}>
              {sql}
            </pre>
          </AccordionDetails>
        </Accordion>
      )}
      {rows && rows.length > 0 && (
        <TableContainer component={Paper} sx={{ maxHeight: 200, overflow: 'auto' }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                {Object.keys(rows[0]).map((key) => (
                  <TableCell key={key} sx={{ fontWeight: 'bold', bgcolor: 'grey.200' }}>{key}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.slice(0, 50).map((row, index) => (
                <TableRow key={index}>
                  {Object.values(row).map((val, idx) => (
                    <TableCell key={idx} sx={{ fontSize: '0.75rem' }}>{String(val)}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {rows && rows.length === 0 && (
        <Typography variant="caption" color="text.secondary" fontStyle="italic">
          결과 데이터가 없습니다.
        </Typography>
      )}
    </Box>
  );
};


const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState('analysis');
  const [adminTab, setAdminTab] = useState(0); // 0 for Semantic Metadata, 1 for Knowledge Cards
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState('');
  const [useMock, setUseMock] = useState(true); // Default to mock mode for demonstration
  const [mockScenarios, setMockScenarios] = useState<MockScenario[]>([]); // State for mock scenarios
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const apiBaseUrl = import.meta.env?.VITE_API_BASE_URL ?? 'http://localhost:8000';

  // Fetch mock scenarios on component mount
  useEffect(() => {
    const fetchMockScenarios = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/mock_scenarios`);
        if (response.ok) {
          const data = await response.json();
          setMockScenarios(data);
        }
      } catch (error) {
        console.error("Failed to fetch mock scenarios:", error);
      }
    };
    fetchMockScenarios();
  }, [apiBaseUrl]);


  const nlqMutation = useMutation<NlqResponse, Error, NlqRequest>({
    mutationFn: async (requestData: NlqRequest) => {
      const response = await fetch(`${apiBaseUrl}/api/nlq`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'API 요청에 실패했습니다.');
      }
      return response.json();
    },
    onSuccess: (data) => {
      setChatHistory((prev) => [...prev, { role: 'bot', content: data }]);
    },
    onError: (error) => {
      setChatHistory((prev) => [...prev, { role: 'bot', content: { error: error.message } }]);
    },
  });

  // Extract last successful NLQ response for visualization
  const lastNlqResponse: NlqResponse | undefined = chatHistory.slice().reverse().find(
    msg => msg.role === 'bot' && typeof msg.content !== 'string' && !('error' in msg.content)
  )?.content as NlqResponse | undefined;


  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory, nlqMutation.isPending]);

  const handleSendMessage = (message?: string | MockScenario) => {
    // Handle free-form text input from the text field
    if (!message) {
      if (!userInput.trim()) return;
      setChatHistory((prev) => [...prev, { role: 'user', content: userInput }]);
      nlqMutation.mutate({ question: userInput, two_stage: true, execute: true, interpret: true, direct: false, use_mock: useMock });
      setUserInput('');
      return;
    }
    
    // Handle button clicks (which can be a string or a MockScenario object)
    const question = typeof message === 'string'
      ? message
      : (message.text || message.question || '');
    const mock_planner_file = typeof message === 'object' ? message.planner_file : undefined;
    const mock_coder_file = typeof message === 'object' ? message.coder_file : undefined;
    const mock_data_ref = typeof message === 'object' ? message.data_ref : undefined;
    if (!question.trim()) {
      return;
    }

    setChatHistory((prev) => [...prev, { role: 'user', content: question }]);
    setUserInput('');
    nlqMutation.mutate({
      question: question,
      two_stage: true,
      execute: true,
      interpret: true,
      direct: false, // Always use MCP
      use_mock: useMock,
      mock_data_ref,
      mock_planner_file,
      mock_coder_file,
    });
  };

  // 시뮬레이션용 데이터
  const reliabilityScore = 98.5; // This is not used anywhere else for now.
  const lastUpdated = "2026-01-09 05:00";


  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${drawerWidth}px)`,
          ml: `${drawerWidth}px`,
          bgcolor: 'white',
          boxShadow: 'none',
          borderBottom: '1px solid',
          borderColor: 'grey.200',
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="h6" noWrap component="div" color="text.primary">
              {activeTab === 'dashboard' && '데일리 브리핑'}
              {activeTab === 'analysis' && '심층 분석 (Drill-down)'}
              {activeTab === 'admin' && '시맨틱/지식 관리'}
            </Typography>
            <Chip
              icon={<AccessTimeIcon fontSize="small" />}
              label={`최종 업데이트: ${lastUpdated}`}
              size="small"
              sx={{ bgcolor: 'grey.100', color: 'grey.600', fontSize: '0.75rem' }}
            />
          </Box>
          <Box display="flex" alignItems="center" gap={2}>
            <Box textAlign="right">
              <Typography variant="body2" fontWeight="bold" color="text.primary">경기도 데이터분석과</Typography>
              <Typography variant="caption" color="text.secondary">홍길동 사무관</Typography>
            </Box>
            <AccountCircleIcon sx={{ fontSize: 40, color: 'primary.main' }} />
          </Box>
        </Toolbar>
      </AppBar>
      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            bgcolor: 'grey.900',
            color: 'common.white',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Box sx={{ p: 3, borderBottom: '1px solid', borderColor: 'grey.800' }}>
          <Typography variant="h5" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'info.main' }}>
            <ChatIcon fontSize="large" color="info" />
            경기도 인구 AI
          </Typography>
          <Typography variant="caption" sx={{ color: 'grey.400', textTransform: 'uppercase', letterSpacing: 1 }}>
            Administrative Intelligence
          </Typography>
        </Box>
        <List sx={{ color: 'grey.300' }}>
          <ListItem disablePadding>
            <ListItemButton
              selected={activeTab === 'dashboard'}
              onClick={() => setActiveTab('dashboard')}
              sx={{
                '&.Mui-selected': { bgcolor: 'primary.dark', color: 'common.white' },
                '&.Mui-selected:hover': { bgcolor: 'primary.dark' },
                '&:hover': { bgcolor: 'grey.800' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}><DashboardIcon /></ListItemIcon>
              <ListItemText primary="데일리 브리핑" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton
              selected={activeTab === 'analysis'}
              onClick={() => setActiveTab('analysis')}
              sx={{
                '&.Mui-selected': { bgcolor: 'primary.dark', color: 'common.white' },
                '&.Mui-selected:hover': { bgcolor: 'primary.dark' },
                '&:hover': { bgcolor: 'grey.800' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}><ChatIcon /></ListItemIcon>
              <ListItemText primary="심층 분석 (Drill-down)" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton
              selected={activeTab === 'admin'}
              onClick={() => setActiveTab('admin')}
              sx={{
                '&.Mui-selected': { bgcolor: 'primary.dark', color: 'common.white' },
                '&.Mui-selected:hover': { bgcolor: 'primary.dark' },
                '&:hover': { bgcolor: 'grey.800' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}><SettingsIcon /></ListItemIcon>
              <ListItemText primary="시맨틱/지식 관리" />
            </ListItemButton>
          </ListItem>
        </List>
        <Box sx={{ flexGrow: 1 }} />
        <Box sx={{ p: 2, bgcolor: 'grey.800', m: 2, borderRadius: 2 }}>
          <Grid container spacing={1}>
            <Grid item xs={6}>
              <Chip
                label="시스템 상태: 정상"
                size="small"
                sx={{ bgcolor: 'success.dark', color: 'common.white', width: '100%', justifyContent: 'flex-start' }}
                icon={<CheckCircleIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6}>
              <Chip
                label="API 서버: 정상"
                size="small"
                sx={{ bgcolor: 'success.dark', color: 'common.white', width: '100%', justifyContent: 'flex-start' }}
                icon={<CheckCircleIcon fontSize="small" />}
              />
            </Grid>
          </Grid>
        </Box>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8, bgcolor: 'grey.50', minHeight: 'calc(100vh - 64px)' }}>
        {activeTab === 'dashboard' && (
          <Container maxWidth="lg">
            <DailyBriefing /> {/* Integrate DailyBriefing component */}
          </Container>
        )}
        {activeTab === 'analysis' && (
          <Container maxWidth="xl" sx={{ height: 'calc(100vh - 120px)', display: 'flex', gap: 3 }}>
            {/* Visualization Area */}
            {lastNlqResponse && lastNlqResponse.rows && lastNlqResponse.rows.length > 0 ? (
              <ChartRenderer rows={lastNlqResponse.rows} plan={lastNlqResponse.plan} />
            ) : (
              <Paper elevation={1} sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'grey.100' }}>
                <Box textAlign="center" p={4} sx={{ bgcolor: 'white', borderRadius: 2, boxShadow: 1 }}>
                  <BarChartIcon sx={{ fontSize: 60, color: 'grey.300', mb: 2 }} />
                  <Typography variant="body1" color="text.secondary">분석 결과에 따른 시각화 자료가 여기에 표시됩니다.</Typography>
                  <Typography variant="caption" color="text.disabled">(데이터 없음 또는 UI 목업 상태)</Typography>
                </Box>
              </Paper>
            )}

            {/* Chat Area */}
            <Paper elevation={1} sx={{ width: 480, display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'grey.200', bgcolor: 'grey.50' }}>
                <Typography variant="subtitle1" fontWeight="bold">AI 분석관 대화</Typography>
              </Box>
              <Box ref={chatContainerRef} sx={{ flexGrow: 1, p: 2, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
                {chatHistory.map((chat, index) => (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      justifyContent: chat.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        maxWidth: '80%',
                        bgcolor: chat.role === 'user' ? 'primary.main' : 'grey.100',
                        color: chat.role === 'user' ? 'common.white' : 'text.primary',
                        ...(chat.role === 'user'
                          ? { borderBottomRightRadius: 0 }
                          : { borderBottomLeftRadius: 0 }),
                      }}
                    >
                      {typeof chat.content === 'string' ? (
                        <Typography variant="body2">{chat.content}</Typography>
                      ) : (
                        <BotResponse response={chat.content} />
                      )}
                    </Box>
                  </Box>
                ))}
                {nlqMutation.isPending && (
                  <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <Box sx={{ p: 1.5, borderRadius: 2, borderBottomLeftRadius: 0, bgcolor: 'grey.100' }}>
                      <CircularProgress size={20} />
                    </Box>
                  </Box>
                )}
              </Box>
              <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'grey.200', bgcolor: 'white' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="caption" color="text.secondary">질의 실행</Typography>
                  <FormControlLabel // Added for Mock Mode
                    control={
                      <Switch
                        size="small"
                        checked={useMock}
                        onChange={(event) => setUseMock(event.target.checked)}
                      />
                    }
                    label={<Typography variant="caption">Mock 모드</Typography>}
                  />
                </Box>
                {useMock ? (
                  <>
                    <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                      Mock 질문 예시
                    </Typography>
                    <Grid container spacing={1} sx={{ mb: 1 }}>
                      {mockScenarios.length ? (
                        mockScenarios.map((scenario, i) => (
                          <Grid item key={i}>
                            <Button
                              variant="outlined"
                              size="small"
                              onClick={() => handleSendMessage(scenario)}
                              sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                            >
                          {scenario.text || scenario.question}
                        </Button>
                          </Grid>
                        ))
                      ) : (
                        <Grid item>
                          <Typography variant="caption" color="text.secondary">
                            사용 가능한 시나리오가 없습니다.
                          </Typography>
                        </Grid>
                      )}
                    </Grid>
                  </>
                ) : (
                  <>
                    <Typography variant="caption" color="text.secondary">
                      Live LLM 예시
                    </Typography>
                    <Grid container spacing={1} sx={{ mt: 0.5, mb: 1 }}>
                      {[
                        '성남시 최근 3년 동일 기간 유입 인구 비교',
                        '수원시 팔달구 30대 여성 인구',
                      ].map((q, i) => (
                        <Grid item key={i}>
                          <Button
                            variant="outlined"
                            size="small"
                            color="secondary"
                            onClick={() => handleSendMessage(q)}
                            sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                          >
                            {q}
                          </Button>
                        </Grid>
                      ))}
                    </Grid>
                  </>
                )}
                <Divider sx={{ my: 1 }} />
                <TextField
                  fullWidth
                  variant="outlined"
                  placeholder="분석할 내용을 입력하세요..."
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !nlqMutation.isPending) {
                      handleSendMessage();
                    }
                  }}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => handleSendMessage()}
                          disabled={nlqMutation.isPending}
                          edge="end"
                          color="primary"
                        >
                          <SendIcon />
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>
            </Paper>
          </Container>
        )}
        {activeTab === 'admin' && (
          <Container maxWidth="xl" sx={{ mt: 2 }}>
            <Typography variant="h5" gutterBottom>시맨틱/지식 관리</Typography>
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs value={adminTab} onChange={(event, newValue) => setAdminTab(newValue)} aria-label="admin tabs">
                <Tab label="Semantic Metadata" icon={<DescriptionIcon />} iconPosition="start" />
                <Tab label="Knowledge Cards" icon={<HistoryEduIcon />} iconPosition="start" />
              </Tabs>
            </Box>
            {adminTab === 0 && <SemanticMetadataTable />}
            {adminTab === 1 && <KnowledgeCardTable />}
          </Container>
        )}
      </Box>
    </Box>
  );
};

export default App;
