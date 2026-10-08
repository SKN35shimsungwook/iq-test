import json

data = {
    "title": "디지털 인지 평가 시스템 개발을 위한 심리측정학적·기술적·법률적 요건 종합 보고서",
    "overview": "지능 검사(IQ Test)를 디지털 소프트웨어 형태로 구축하는 작업은 단순한 설문 시스템 개발을 넘어 심리측정학(Psychometrics), 데이터 과학, 소프트웨어 아키텍처, 그리고 규제 법률이 복합적으로 교차하는 고도의 시스템 공학 프로젝트이다. 신뢰성과 타당성을 고루 갖춘 인지 평가 프로그램을 개발하기 위해서는 검사의 이론적 기반인 인지 능력 모델링부터 문항 반응 이론(IRT) 기반 컴퓨터 맞춤형 검사(CAT) 알고리즘 구축, 편차 IQ 및 연속 규준 산정, 고정밀 프론트엔드/백엔드 아키텍처 설계, 그리고 저작권과 개인정보보호법에 이르는 법적 규제 준수까지 다각도의 요소를 체계적으로 설계해야 한다.",
    "sections": [
        {
            "section_id": 1,
            "title": "심리학적 이론 프레임워크 및 인지 영역 구조화",
            "description": "지능 검사 프로그램의 심리측정학적 타당도는 검사가 기반을 두고 있는 인지 능력 이론 모델의 엄밀성에 의해 결정된다. 현대 인지 심리학 및 평가학 분야에서 가장 광범위하게 검증되고 공인된 지능 구조 모델은 카텔-혼-카롤(Cattell-Horn-Carroll, 이하 CHC) 이론이다.",
            "chc_framework": {
                "definition": "CHC 이론은 Raymond Cattell과 John Horn의 유동적-결정적 지능(Gf-Gc) 모델과 John Carroll의 3계층(Three-Stratum) 요인 분석 이론을 통합하여 수립된 다차원 위계 구조이다. 웩슬러 성인 지능 검사(WAIS-IV), 아동용 지능 검사(WISC-V), 우드콕-존슨 검사(WJ-IV), 스탠퍼드-비네 5판(SB5) 등 현대의 주요 임상 지능 검사 배터리는 모두 CHC 프레임워크를 표준 기틀로 삼아 출제 및 해석 체계를 구성하고 있다.",
                "strata": [
                    {
                        "layer": "Stratum III",
                        "name": "최상위 계층",
                        "description": "모든 인지적 수행에 바탕이 되는 단일 요인인 일반 지능 요인(g factor)"
                    },
                    {
                        "layer": "Stratum II",
                        "name": "중간 계층",
                        "description": "8개에서 16개 사이의 광범위 인지 능력(Broad Abilities) 영역으로 구성되며, 하위 검사 개발의 직접적인 기준이 됨"
                    },
                    {
                        "layer": "Stratum I",
                        "name": "최하위 계층",
                        "description": "광범위 능력 하위에 존재하는 70~80개 이상의 세부 한정 능력(Narrow Abilities)으로 구성"
                    }
                ],
                "broad_abilities": [
                    {
                        "name": "유동적 추론",
                        "code": "Gf",
                        "definition": "문화적·학습적 경험에 의존하지 않고 신규 문제 상황에서 귀납적·연역적 논리를 적용하는 능력",
                        "implementation_tasks": "행렬 추론(Matrix Reasoning), 도형 무게 비교(Figure Weights), 수열 논리"
                    },
                    {
                        "name": "결정적 지능 / 이해-지식",
                        "code": "Gc",
                        "definition": "특정 문화권 내에서 습득한 언어적 지식, 어휘력, 사회적 개념 형성 및 범주화 능력",
                        "implementation_tasks": "어휘 검사, 공통성 찾기(Similarities), 상식 문제"
                    },
                    {
                        "name": "작업 기억",
                        "code": "Gwm",
                        "definition": "외부 자극 정보를 단기 수용 영역에 유지하면서 능동적으로 조작 및 재구성하는 능력",
                        "implementation_tasks": "숫자 외우기(Digit Span), 문자에순서 정렬, 산수 과제"
                    },
                    {
                        "name": "시공간 처리",
                        "code": "Gv",
                        "definition": "시각적 자극 및 공간적 형상을 생성, 저장, 회전, 변형하여 처리하는 능력",
                        "implementation_tasks": "토막 짜기(Block Design), 시각 퍼즐(Visual Puzzles), Mental Rotation"
                    },
                    {
                        "name": "처리 속도",
                        "code": "Gs",
                        "definition": "간단하고 반복적인 시각적 심볼 과제를 주의집중을 유지하며 신속·정확하게 수행하는 능력",
                        "implementation_tasks": "기호 쓰기(Coding), 기호 탐색(Symbol Search)"
                    },
                    {
                        "name": "정량적 추론",
                        "code": "Gq",
                        "definition": "수리적 개념 및 데이터 간의 논리적 관계를 이해하고 수리 과제를 해결하는 능력",
                        "implementation_tasks": "응용 수리 계산, 수치 추론, 수열 규칙 찾기"
                    }
                ]
            },
            "profile_analysis": {
                "full_scale_iq": "단일 지표인 전체 IQ(Full-Scale IQ, FSIQ)는 모든 하위 검사의 공통 변량을 통합하여 일반 지능 요인(g)을 추정한 통계적 수치이다. 통계적 안정성을 제공하지만 세부 인지 영역 간 불균형을 은폐할 수 있음.",
                "recommendation": "CHC 광범위 능력 영역별로 세분화된 지수 점수(Index Scores)와 신뢰구간을 다차원 인지 프로파일 형태로 제공해야 함."
            }
        },
        {
            "section_id": 2,
            "title": "문항 반응 이론(IRT) 및 컴퓨터 맞춤형 검사(CAT) 엔진 설계",
            "description": "전통적인 고정형 종이 검사의 한계를 극복하기 위해 문항 반응 이론(IRT) 기반 컴퓨터 맞춤형 검사(CAT) 엔진을 채택한다.",
            "irt_modeling": {
                "model_used": "3-Parameter Logistic Model (3PL)",
                "formula": "P_i(theta) = c_i + (1 - c_i) / (1 + e^(-D * a_i * (theta - b_i)))",
                "parameters": {
                    "theta": "검사 대상자의 잠재적 인지 능력 매개변수 (N(0,1) 상의 연속 변수)",
                    "b_i": "문항 난이도 매개변수 (추측 없을 때 정답률 50% 지점)",
                    "a_i": "문항 변별도 매개변수 (로지스틱 곡선의 경사도)",
                    "c_i": "추측도 매개변수 (무작위 추측으로 정답을 맞힐 하한 확률)",
                    "D": "척도 상수 (1.7 또는 1.0)"
                },
                "other_models": {
                    "1PL_Rasch": "a_i=1, c_i=0 고정",
                    "2PL": "c_i=0 고정"
                }
            },
            "cat_pipeline": {
                "item_pool": "사전 예비 검사(Pilot Test)를 통해 수집된 데이터를 바탕으로 IRT 파라미터가 보정된 문항 은행 구축",
                "initialization": "초기 능력 추정값 theta_0 = 0.0, 중간 난이도(b_i ≈ 0.0) 문항 제시",
                "item_selection": {
                    "method": "Maximum Fisher Information (MFI)",
                    "formula": "I_i(theta) = (P'_i(theta))^2 / (P_i(theta) * (1 - P_i(theta)))"
                },
                "scoring_algorithm": "Maximum Likelihood Estimation (MLE) 또는 Bayesian Estimation (EAP, MAP)",
                "termination_criteria": [
                    "추정 오차의 표준편차 SEM(theta) = 1 / sqrt(sum(I_i(theta))) <= threshold (예: SEM <= 0.30)",
                    "최대 문항 수 도달 (예: 영역당 20문항)"
                ]
            },
            "frameworks": [
                {
                    "name": "catsim",
                    "language": "Python",
                    "irt_models": "1PL, 2PL, 3PL",
                    "features": "MFI 문항 선택, EAP/MAP/MLE 능력 추정, SEM 기반 검사 종료 등 CAT 전과정 지원. FastAPI/Django 연동 최적."
                },
                {
                    "name": "EduCAT",
                    "language": "Python",
                    "irt_models": "IRT, MIRT, NCD",
                    "features": "신경망 기반 인지 진단 모델(Neural-CAT, BOBCAT) 및 다차원 IRT 구현 지원."
                },
                {
                    "name": "catIrt",
                    "language": "R",
                    "irt_models": "1PL, 2PL, 3PL",
                    "features": "전통적 심리측정학 알고리즘 수립 및 SPRT, GLR, CI 등 분류 CAT 알고리즘 검증 도구 제공."
                },
                {
                    "name": "mirtCAT",
                    "language": "R",
                    "irt_models": "MIRT (다차원 IRT)",
                    "features": "다차원 CHC 요인 동시 추정 특화, Shiny 기반 GUI 웹 인터페이스 생성 지원."
                },
                {
                    "name": "CATQuiz (Moodle Plugin)",
                    "language": "PHP",
                    "irt_models": "1PL, 2PL, 3PL, GRM, PCM",
                    "features": "LMS 환경 문항 DB 관리, IRT 파라미터 버전 제어 및 adaptive quiz 구동 엔진 제공."
                }
            ]
        },
        {
            "section_id": 3,
            "title": "IQ 점수 표준화 및 연속 규준(Continuous Norming) 산정 연산",
            "deviation_iq_conversion": {
                "iq_formula": "IQ = 100 + 15 * ((hat_theta - mu_theta) / sigma_theta)",
                "scaled_score_formula": "Scaled Score (SS) = 10 + 3 * ((hat_theta - mu_theta) / sigma_theta)",
                "description": "평균 100, 표준편차 15의 편차 IQ 척도로 정규화 변환."
            },
            "continuous_norming": {
                "sampling": "층화 표집(Stratified Sampling)을 통한 대규모 규준 데이터 수집",
                "age_trajectories": {
                    "Gf_Gs": "청소년기~성인 초기에 피크 후 연령 증가에 따라 완만하게 감소",
                    "Gc": "노년기까지 일정 수준 유지 또는 발달"
                },
                "smoothing_method": "경계 불연속성 오차 방지를 위한 다항 회귀 모델 또는 GAMLSS(Generalized Additive Models for Location, Scale and Shape) 알고리즘 적용"
            }
        },
        {
            "section_id": 4,
            "title": "프론트엔드/백엔드 아키텍처 및 기술적 UX/UI 인터페이스",
            "architecture": "클라이언트 애플리케이션, 통신 레이어(REST API / WebSocket), CAT 분석 백엔드 서비스, 데이터베이스 레이어로 분리된 마이크로서비스 아키텍처",
            "frontend_ui_ux": [
                {
                    "feature": "고정밀 타이밍 측정",
                    "implementation": "window.performance.now() API 사용 (나노초/밀리초 정밀도 보장, 반응 시간 측정 오차 방지)"
                },
                {
                    "feature": "벡터 그래픽 자극 렌더링",
                    "implementation": "SVG 또는 Canvas 기반 동적 생성으로 디바이스 해상도에 따른 자극 왜곡 방지"
                },
                {
                    "feature": "피로도 및 진행 관리",
                    "implementation": "지시선, 명확한 지시문 카드, 연습 문항(Practice Items) 단계 제공"
                },
                {
                    "feature": "부정행위 및 AI 방지",
                    "implementation": "CSS user-select: none, 브라우저 이탈 탐지(visibilitychange, blur), Canvas 래스터화 및 노이즈 오버레이"
                }
            ]
        },
        {
            "section_id": 5,
            "title": "저작권 보호 및 개인정보 규제 준수 체계",
            "copyright_compliance": "기존 지능 검사(WAIS, WISC 등) 저작권 침해 방지를 위해 독자적 출제 절차 및 예비 표본 조사를 통한 독립적 IRT 파라미터 산출 필수.",
            "privacy_compliance": {
                "mandatory_notice_items": [
                    "수집·이용 항목",
                    "수집·이용 목적",
                    "보유 및 이용 기간",
                    "동의 거부권 및 불이익 안내",
                    "제3자 제공 내역 (해당 시)",
                    "처리위탁 내역 (해당 시)"
                ],
                "ui_ux_requirements": [
                    {
                        "item": "사전 체크 금지 (Opt-in)",
                        "legal_risk": "체크박스가 사전 선택된 경우 동의 무효",
                        "technical_requirement": "모든 체크박스 초기 상태 checked=false 설정"
                    },
                    {
                        "item": "필수 / 선택 동의 분리",
                        "legal_risk": "통합 동의 시 선택 동의 무효",
                        "technical_requirement": "필수 수집 동의와 선택 마케팅 동의 시각적·기능적 분리"
                    },
                    {
                        "item": "가독성 글자 크기",
                        "legal_risk": "충분한 고지 의무 위반 과태료 위험",
                        "technical_requirement": "모바일 최소 12px, 데스크톱 최소 14px 이상 유지"
                    },
                    {
                        "item": "동의 버튼 명칭",
                        "legal_risk": "모호한 명칭은 명확한 의사 표현으로 미인정",
                        "technical_requirement": "'동의합니다' 또는 '위 내용에 동의합니다'로 명시"
                    },
                    {
                        "item": "만 14세 미만 동의 절차",
                        "legal_risk": "법정대리인 동의 누락 시 법 위반",
                        "technical_requirement": "연령 확인 레이어 및 본인인증 기반 법정대리인 동의 모듈 탑재"
                    }
                ]
            }
        },
        {
            "section_id": 6,
            "title": "결론 및 종합 제언",
            "summary": "CHC 모델 기반 다차원 인지 영역 평가, 3PL IRT 및 CAT 알고리즘(MFI 문항 선택) 탑재, Continuous Norming 기반 편차 IQ 도출, performance.now() 및 보안 UX 적용, 독자 문항 출제 및 개인정보보호법 UI 규정 완비."
        }
    ]
}

# Write file
file_path = "digital_cognitive_assessment_system_report.json"
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"JSON file created successfully: {file_path}")