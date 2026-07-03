import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  MessageSquare, 
  Settings, 
  Copy, 
  TrendingUp, 
  Map as MapIcon, 
  AlertCircle, 
  CheckCircle2, 
  ArrowRight,
  Database,
  Search,
  Users,
  ChevronRight,
  Calendar,
  Zap
} from 'lucide-react';

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [chatStep, setChatStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  // 시뮬레이션용 데이터
  const reliabilityScore = 98.5;
  const lastUpdated = "2026-01-12 09:00";

  // 심층 분석 시나리오 데이터
  const chatScenarios = [
    {
      user: "성남시 삼평동 유입 인구가 왜 갑자기 늘었지?",
      bot: "삼평동 유입 인구를 분석한 결과, 전주 대비 18% 급증하였습니다. 가장 먼저 유입지를 분석해 볼까요?",
      actions: ["유입지 상세 분석", "연령대별 비중 확인"]
    },
    {
      user: "유입지 상세 분석해줘",
      bot: "분석 결과, 서울 강남권(강남/서초) 유입이 32%로 가장 높습니다. 주로 3040 직장인 계층입니다. 인근 행사 정보와 결합해 볼까요?",
      actions: ["주변 행사 데이터 결합", "3개년 추이 비교"]
    },
    {
      user: "주변 행사 데이터 결합",
      bot: "공공데이터 연동 결과, 당일 판교 제2테크노밸리에서 '글로벌 AI 컨퍼런스'가 개최되었습니다. 이로 인한 직장인 유입으로 판단됩니다.",
      actions: ["보고서 초안 생성", "유사 사례 비교"]
    }
  ];

  const handleNextStep = () => {
    if (chatStep < chatScenarios.length - 1) {
      setIsLoading(true);
      setTimeout(() => {
        setChatStep(prev => prev + 1);
        setIsLoading(false);
      }, 800);
    }
  };


  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans">
      {/* 사이드바 */}
      <div className="w-64 bg-slate-900 text-white flex flex-col">
        <div className="p-6 border-b border-slate-800">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Zap className="text-blue-400 fill-blue-400" size={24} />
            경기도 인구 AI
          </h1>
          <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest">Administrative Intelligence</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${activeTab === 'dashboard' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          >
            <LayoutDashboard size={20} />
            데일리 브리핑
          </button>
          <button 
            onClick={() => setActiveTab('analysis')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${activeTab === 'analysis' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          >
            <MessageSquare size={20} />
            심층 분석 (Drill-down)
          </button>
          <button 
            onClick={() => setActiveTab('admin')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${activeTab === 'admin' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          >
            <Settings size={20} />
            시맨틱/지식 관리
          </button>
        </nav>
        
        <div className="p-4 bg-slate-800 m-4 rounded-xl text-xs space-y-2">
          <div className="flex justify-between">
            <span className="text-slate-400">시스템 상태</span>
            <span className="text-emerald-400 flex items-center gap-1 text-[10px]">● 정상 운영중</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">데이터 신뢰도</span>
            <span className="font-bold">{reliabilityScore}%</span>
          </div>
        </div>
      </div>

      {/* 메인 컨텐츠 영역 */}
      <div className="flex-1 overflow-auto flex flex-col">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 sticky top-0 z-10">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-slate-800 capitalize">
              {activeTab === 'dashboard' ? '데일리 브리핑' : activeTab === 'analysis' ? '심층 분석' : '시맨틱/지식 관리'}
            </h2>
            <div className="flex items-center gap-2 bg-slate-100 px-3 py-1 rounded-full text-xs text-slate-500">
              <Calendar size={14} />
              최종 업데이트: {lastUpdated}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right mr-4">
              <p className="text-xs font-bold">경기도 데이터분석과</p>
              <p className="text-[10px] text-slate-400">홍길동 사무관</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
              경기
            </div>
          </div>
        </header>

        <main className="p-8">
          {activeTab === 'dashboard' && (
            <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4">
              <div className="flex justify-between items-end">
                <div>
                  <h3 className="text-2xl font-bold text-slate-800">어제자 경기도 인구 주요 브리핑</h3>
                  <p className="text-slate-500">2026년 1월 11일(일) 기준 분석 리포트입니다.</p>
                </div>
                <button className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 font-medium transition shadow-lg shadow-blue-200">
                  <Copy size={18} />
                  HWP 보고서 문구 복사
                </button>
              </div>

              {/* 지표 카드 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { label: "총 유동인구", value: "1,512.4만", change: "+3.8%", icon: Users, color: "text-blue-600", bg: "bg-blue-50" },
                  { label: "전일 유입 급증 지역", value: "성남시 삼평동", change: "+18.2%", icon: TrendingUp, color: "text-rose-600", bg: "bg-rose-50" },
                  { label: "피크 타임", value: "14:00 - 16:00", change: "주말 휴양형", icon: Zap, color: "text-amber-600", bg: "bg-amber-50" }
                ].map((item, i) => (
                  <div key={i} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-start justify-between">
                    <div>
                      <p className="text-sm text-slate-500 font-medium mb-1">{item.label}</p>
                      <h4 className="text-2xl font-extrabold text-slate-800">{item.value}</h4>
                      <p className={`text-sm mt-2 font-bold ${item.change.startsWith('+') ? 'text-rose-500' : 'text-blue-500'}`}>
                        {item.change} <span className="text-slate-400 font-normal">vs 전주 동일요일</span>
                      </p>
                    </div>
                    <div className={`${item.bg} ${item.color} p-3 rounded-xl`}>
                      <item.icon size={24} />
                    </div>
                  </div>
                ))}
              </div>

              {/* AI 리포트 영역 */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                    <span className="text-sm font-bold flex items-center gap-2">
                      <MessageSquare size={16} className="text-blue-600" />
                      AI 분석관 요약 및 시사점
                    </span>
                    <span className="text-xs text-slate-400 flex items-center gap-1">
                      <CheckCircle2 size={12} className="text-emerald-500" />
                      데이터 정합성 검증 완료
                    </span>
                  </div>
                  <div className="p-8 space-y-6 leading-relaxed text-slate-700">
                    <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg">
                      <p className="font-semibold text-blue-900">핵심 관찰 사항:</p>
                      <p className="text-blue-800 mt-1">성남시 삼평동(판교) 지역의 인구 유입이 전주 동요일 대비 18.2% 급증하였습니다. 이는 일요일임에도 불구하고 특정 산업 행사 또는 대규모 시설 방문객 유입의 가능성을 시사합니다.</p>
                    </div>
                    <div>
                      <h5 className="font-bold text-slate-800 mb-2">1. 유입 및 인구 구조</h5>
                      <p>유입 인구의 주 연령대는 3040 세대로 확인되며, 서울 강남/서초권에서의 유입 비중이 높습니다. 단순 통과 목적보다는 특정 목적지 방문을 위한 유입이 주를 이루고 있습니다.</p>
                    </div>
                    <div>
                      <h5 className="font-bold text-slate-800 mb-2">2. 제언 및 대응 전략</h5>
                      <p>삼평동 주변 상권 및 교통 혼잡도가 예상보다 높게 측정되었습니다. 향후 유사 패턴 발생 시 광역 교통 노선의 탄력적 운영 및 주차 안내 시스템 강화가 필요합니다.</p>
                    </div>
                    <div className="pt-6 border-t border-slate-100 flex items-center justify-between">
                      <p className="text-xs text-slate-400">※ 본 리포트는 행정표준코드 KIKmix 및 SKT 유동인구 데이터를 기반으로 자동 생성되었습니다.</p>
                      <button onClick={() => setActiveTab('analysis')} className="text-blue-600 text-sm font-bold flex items-center gap-1 hover:underline">
                        심층 분석 이동 <ChevronRight size={16} />
                      </button>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
                  <h5 className="font-bold text-slate-800 border-b pb-4">오늘의 분석 추천</h5>
                  <div className="space-y-4">
                    {[
                      { title: "성남시 삼평동 심층 분석", desc: "유입 원인 및 연령대 상세 파악", status: "Hot" },
                      { title: "수원역 환승 센터 혼잡도", desc: "교차로 소통 데이터 결합 분석", status: "Steady" },
                      { title: "광교 호수공원 주말 패턴", desc: "주변 시설 및 상권 유입 대조", status: "New" }
                    ].map((rec, i) => (
                      <div key={i} className="group cursor-pointer p-4 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50 transition">
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-semibold text-sm group-hover:text-blue-600">{rec.title}</span>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${rec.status === 'Hot' ? 'bg-rose-100 text-rose-600' : 'bg-slate-100 text-slate-500'}`}>{rec.status}</span>
                        </div>
                        <p className="text-xs text-slate-400 leading-tight">{rec.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'analysis' && (
            <div className="max-w-7xl mx-auto h-[calc(100vh-180px)] flex gap-6 animate-in fade-in zoom-in-95 duration-300">
              {/* 시각화 영역 */}
              <div className="flex-1 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b flex items-center justify-between bg-slate-50">
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-bold flex items-center gap-2 uppercase tracking-tight">
                      <MapIcon size={16} className="text-blue-600" />
                      인터랙티브 분석 캔버스
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button className="text-xs px-3 py-1 bg-white border rounded shadow-sm hover:bg-slate-50">지도</button>
                    <button className="text-xs px-3 py-1 bg-blue-600 text-white rounded shadow-sm">차트</button>
                  </div>
                </div>
                <div className="flex-1 p-8 flex items-center justify-center relative bg-slate-100">
                  <div className="w-full h-full bg-white rounded-xl shadow-inner flex flex-col items-center justify-center p-8">
                     {chatStep === 0 && (
                        <div className="text-center">
                          <Users size={64} className="text-slate-200 mb-4 mx-auto" />
                          <p className="text-slate-400 font-medium">분석 대화를 통해 심층 데이터를 확인하세요.</p>
                        </div>
                     )}
                     {chatStep === 1 && (
                        <div className="w-full h-full flex flex-col">
                          <h6 className="text-sm font-bold mb-4">삼평동 유입지별 비중 (TOP 5)</h6>
                          <div className="space-y-4 flex-1 flex flex-col justify-center">
                            {[
                              { label: "서울 강남구", value: "22%", w: "w-[80%]" },
                              { label: "서울 서초구", value: "12%", w: "w-[45%]" },
                              { label: "용인시 수지구", value: "9%", w: "w-[35%]" },
                              { label: "성남시 분당구", value: "7%", w: "w-[25%]" },
                              { label: "기타", value: "50%", w: "w-[15%]" }
                            ].map((item, i) => (
                              <div key={i} className="space-y-1">
                                <div className="flex justify-between text-xs">
                                  <span className="font-medium text-slate-600">{item.label}</span>
                                  <span className="font-bold text-blue-600">{item.value}</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                  <div className={`h-full bg-blue-500 ${item.w} transition-all duration-1000`}></div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                     )}
                     {chatStep >= 2 && (
                        <div className="w-full h-full flex flex-col">
                           <h6 className="text-sm font-bold mb-4">시간대별 유동인구 및 행사 연동 (삼평동)</h6>
                           <div className="flex-1 flex items-end gap-2 pb-8">
                             {[30, 35, 40, 42, 55, 85, 98, 75, 50, 40, 35, 30].map((h, i) => (
                               <div key={i} className="flex-1 group relative">
                                  <div 
                                    className={`w-full rounded-t-lg transition-all duration-500 ${i === 6 ? 'bg-rose-500 shadow-lg shadow-rose-200' : 'bg-blue-400 opacity-60'}`} 
                                    style={{ height: `${h}%` }}
                                  ></div>
                                  <div className="absolute -bottom-6 left-0 right-0 text-[10px] text-center text-slate-400">{i+10}시</div>
                                  {i === 6 && (
                                    <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] p-2 rounded whitespace-nowrap shadow-xl z-20">
                                      행사 피크 탐지
                                    </div>
                                  )}
                                </div>
                             ))}
                           </div>
                           <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg flex items-center gap-3">
                              <AlertCircle className="text-amber-500" size={16} />
                              <span className="text-xs text-amber-800 font-medium">교류 분석: 판교역 하차 인구와 삼평동 유입 간 상관관계 0.92</span>
                           </div>
                        </div>
                     )}
                  </div>
                </div>
              </div>

              {/* 채팅 영역 */}
              <div className="w-96 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col">
                <div className="p-4 border-b bg-slate-50 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-500">AI 분석관 모드</span>
                </div>
                
                <div className="flex-1 p-4 overflow-auto space-y-4">
                  {chatScenarios.slice(0, chatStep + 1).map((chat, i) => (
                    <div key={i} className="space-y-4">
                      <div className="flex justify-end">
                        <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl rounded-tr-none text-sm max-w-[85%] shadow-sm">
                          {chat.user}
                        </div>
                      </div>
                      <div className="flex justify-start">
                        <div className="bg-slate-100 text-slate-800 px-4 py-3 rounded-2xl rounded-tl-none text-sm max-w-[85%] border border-slate-200">
                          {isLoading && i === chatStep ? (
                            <span className="flex gap-1 py-1">
                              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
                              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                            </span>
                          ) : (
                            chat.bot
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-4 border-t space-y-3 bg-slate-50">
                  <p className="text-[10px] text-slate-400 font-bold uppercase ml-1">다음 단계 분석 추천</p>
                  <div className="flex flex-wrap gap-2">
                    {chatScenarios[chatStep].actions.map((action, i) => (
                      <button 
                        key={i}
                        onClick={handleNextStep}
                        className="text-xs bg-white border border-slate-200 hover:border-blue-500 hover:text-blue-600 px-3 py-2 rounded-lg transition-all flex items-center gap-1 shadow-sm font-medium"
                      >
                        {action}
                        <ArrowRight size={12} />
                      </button>
                    ))}
                  </div>
                  <div className="relative mt-2">
                    <input 
                      type="text" 
                      placeholder="분석 질문을 입력하세요..." 
                      className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 pr-10 text-sm focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
                    />
                    <button className="absolute right-3 top-1/2 -translate-y-1/2 text-blue-600 hover:scale-110 transition">
                      <ArrowRight size={18} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'admin' && (
            <div className="max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-top-4">
              <div className="flex justify-between items-center">
                <h3 className="text-2xl font-bold text-slate-800">시맨틱 및 지식 베이스 관리</h3>
                <div className="flex gap-2">
                  <span className="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full text-xs font-bold">시스템 연동 정상</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
                  <div className="p-4 border-b bg-slate-50 font-bold text-sm flex items-center gap-2">
                    <Database size={16} className="text-blue-600" />
                    데이터 카탈로그
                  </div>
                  <div className="p-4 bg-slate-100 border-b relative">
                    <Search className="absolute left-7 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                    <input type="text" placeholder="테이블 검색..." className="w-full text-xs rounded-lg border-none pl-10 focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div className="flex-1 overflow-auto">
                    {[
                      { name: "skt_pcell_pop_daily", type: "민간(SKT)", status: "정상" },
                      { name: "place_codes_history", type: "행정표준", status: "업데이트 필요" },
                      { name: "gyeonggi_bus_inflow", type: "공공(교통)", status: "정상" },
                      { name: "festival_master_data", type: "공공(문화)", status: "정상" }
                    ].map((table, i) => (
                      <div key={i} className="p-4 hover:bg-slate-50 border-b last:border-0 cursor-pointer transition group">
                        <div className="flex justify-between mb-1">
                          <span className="text-sm font-mono font-bold text-slate-700 group-hover:text-blue-600">{table.name}</span>
                          <span className={`text-[10px] font-bold ${table.status === '정상' ? 'text-emerald-500' : 'text-amber-500'}`}>{table.status}</span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{table.type}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="md:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
                  <div className="p-4 border-b bg-slate-50 font-bold text-sm flex justify-between items-center">
                    <span className="flex items-center gap-2">
                      <Settings size={16} className="text-blue-600" />
                      시맨틱 설정: <span className="text-blue-600 font-mono">skt_pcell_pop_daily</span>
                    </span>
                    <button className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-xs font-bold shadow-md shadow-blue-100 hover:bg-blue-700">변경사항 저장</button>
                  </div>
                  <div className="flex-1 p-6 space-y-6 overflow-auto">
                    <div className="space-y-4">
                      <h6 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <MessageSquare size={14} />
                        LLM 비즈니스 해석 규칙
                      </h6>
                      <textarea 
                        className="w-full h-24 p-4 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed"
                        defaultValue="성남시 서비스 유동인구 통계 데이터입니다. 분석 시 반드시 'place_codes' 테이블과 조인하여 현재 유효한 행정동 명칭을 사용해야 하며, 전주 대비 15% 이상 증감 시 '특이 동향'으로 보고서에 기술하십시오."
                      ></textarea>
                    </div>

                    <div className="space-y-4">
                      <h6 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <MapIcon size={14} />
                        지역 지식 카드 관리
                      </h6>
                      <div className="grid grid-cols-2 gap-4">
                        {[
                          { title: "판교 제1테크노밸리", tags: ["#IT집적", "#직장인"], desc: "평일 09-18시 사이 유입 인구의 70%가 직장인으로 구성됨." },
                          { title: "광교 중앙역 인근", tags: ["#행정타운", "#상권"], desc: "경기도청 이전 후 평일 주간 행정 목적 유입 급증세." }
                        ].map((card, i) => (
                          <div key={i} className="p-4 border border-slate-200 rounded-xl space-y-2 relative group hover:border-blue-400 transition bg-white">
                            <div className="flex justify-between">
                              <span className="text-sm font-bold">{card.title}</span>
                              <Settings size={14} className="text-slate-300 group-hover:text-blue-500 cursor-pointer" />
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {card.tags.map((tag, j) => <span key={j} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">{tag}</span>)}
                            </div>
                            <p className="text-xs text-slate-400 leading-tight">{card.desc}</p>
                          </div>
                        ))}
                      </div>
                      <button className="text-xs text-blue-600 font-bold border-2 border-dashed border-blue-100 w-full py-4 rounded-xl hover:bg-blue-50 transition">+ 새로운 지식 개체 추가</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
