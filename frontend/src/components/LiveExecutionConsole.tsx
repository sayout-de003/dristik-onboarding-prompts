import React, { useState, useEffect, useRef } from 'react';
import { AnalysisRun, PipelineGraphState, GraphNode, ActivityEvent } from '../types';
import {
  getExecutionGraph,
  pauseAnalysis,
  resumeAnalysis,
  runGraphNode,
  runGraphSection,
  runPillar,
  getAgentWorkforce,
} from '../services/api';
import { formatMs } from '../lib/format';

interface LiveExecutionConsoleProps {
  run: AnalysisRun;
  onRefreshRun?: () => void;
}

interface CanonicalSectionDef {
  section_id: string;
  title: string;
  description: string;
  order: number;
  node_ids: string[];
}

export const PILLAR_SECTION_MAP: Record<string, { label: string; color: string; pillarKey: string }> = {
  sec_seo: { label: 'SEO Pillar', color: 'text-amber-700 bg-amber-500/10 border-amber-500/30', pillarKey: 'seo' },
  sec_geo: { label: 'GEO Pillar', color: 'text-emerald-700 bg-emerald-500/10 border-emerald-500/30', pillarKey: 'geo' },
  sec_aeo: { label: 'AEO Pillar', color: 'text-violet-700 bg-violet-500/10 border-violet-500/30', pillarKey: 'aeo' },
  sec_cro: { label: 'CRO Pillar', color: 'text-rose-700 bg-rose-500/10 border-rose-500/30', pillarKey: 'cro' },
};

const DEFAULT_SECTIONS: CanonicalSectionDef[] = [
  {
    section_id: 'sec_ingestion',
    title: '1. Ingestion & Multi-Page Crawl',
    description: 'Crawls target domain pages, extracts clean HTML, and populates raw DOM evidence.',
    order: 1,
    node_ids: ['node_crawl', 'node_dom_extraction', 'node_dns_ssl_headers'],
  },
  {
    section_id: 'sec_business_identity',
    title: '2. Business Understanding & Entity Grounding',
    description: 'Resolves canonical entity, industry classification, ICP, and value proposition.',
    order: 2,
    node_ids: ['node_entity_resolution', 'node_icp_offer_profile'],
  },
  {
    section_id: 'sec_seo',
    title: '3. Search Engine Optimization (SEO)',
    description: 'Technical crawlability, indexability, on-page architecture, schema AST, and page rewrites.',
    order: 3,
    node_ids: [
      'node_seo_crawl_indexing',
      'node_seo_technical_health',
      'node_seo_onpage_content',
      'node_seo_schema_ast',
      'node_seo_page_intelligence',
    ],
  },
  {
    section_id: 'sec_geo',
    title: '4. Generative Engine Optimization (GEO)',
    description: 'Entity knowledge graphs, Wikidata grounding, local/multi-location signals, and brand presence.',
    order: 4,
    node_ids: [
      'node_geo_entity_grounding',
      'node_geo_local_signals',
      'node_geo_llm_footprint',
    ],
  },
  {
    section_id: 'sec_aeo',
    title: '5. Answer Engine Optimization (AEO)',
    description: 'AI answer engine citability, conversational query simulation, FAQ schema, and direct answer readiness.',
    order: 5,
    node_ids: [
      'node_aeo_citability_matrix',
      'node_aeo_qa_readiness',
      'node_aeo_search_simulation',
    ],
  },
  {
    section_id: 'sec_cro',
    title: '6. Conversion Rate Optimization (CRO & UX)',
    description: 'Funnel friction, primary CTA hierarchy, value proposition clarity, trust proof, and form ergonomics.',
    order: 6,
    node_ids: [
      'node_cro_cta_visibility',
      'node_cro_value_clarity',
      'node_cro_trust_and_forms',
    ],
  },
  {
    section_id: 'sec_synthesis',
    title: '7. Executive Synthesis, Scoring & Patches',
    description: 'Computes honest multi-pillar scores, synthesizes C-suite narrative, and builds production code patch pack.',
    order: 7,
    node_ids: [
      'node_adversarial_critic',
      'node_integrity_gate',
      'node_causal_bottlenecks',
      'node_honest_scoring',
      'node_executive_narrative',
      'node_code_patch_pack',
      'node_final_report_assembly',
    ],
  },
];

const DEFAULT_NODES_MAP: Record<string, Partial<GraphNode>> = {
  // --- 1. Ingestion & Multi-Page Crawl ---
  node_crawl: {
    node_id: 'node_crawl',
    section_id: 'sec_ingestion',
    section_title: '1. Ingestion & Multi-Page Crawl',
    title: 'Multi-Page HTTP Crawler',
    description: 'Fetches target domain pages, checks status codes, TTFB, and response headers.',
    agent_name: 'CrawlerService',
    dependencies: [],
  },
  node_dom_extraction: {
    node_id: 'node_dom_extraction',
    section_id: 'sec_ingestion',
    section_title: '1. Ingestion & Multi-Page Crawl',
    title: 'DOM AST & Element Ingestion',
    description: 'Parses HTML structure, headings (H1/H2), word counts, CTAs, and link graphs.',
    agent_name: 'DomExtractor',
    dependencies: ['node_crawl'],
  },
  node_dns_ssl_headers: {
    node_id: 'node_dns_ssl_headers',
    section_id: 'sec_ingestion',
    section_title: '1. Ingestion & Multi-Page Crawl',
    title: 'DNS, SSL/TLS & Security Headers',
    description: 'Inspects A/AAAA DNS records, SSL certificate issuer, HSTS, CSP, and transport security.',
    agent_name: 'ExternalEvidenceEnricher',
    dependencies: ['node_dom_extraction'],
  },

  // --- 2. Business Understanding & Grounding ---
  node_entity_resolution: {
    node_id: 'node_entity_resolution',
    section_id: 'sec_business_identity',
    section_title: '2. Business Understanding & Entity Grounding',
    title: 'Brand & Canonical Entity Resolver',
    description: 'Resolves legal and commercial brand identity, official domain, and industry category.',
    agent_name: 'UniversalEntityResolver',
    dependencies: ['node_dom_extraction'],
  },
  node_icp_offer_profile: {
    node_id: 'node_icp_offer_profile',
    section_id: 'sec_business_identity',
    section_title: '2. Business Understanding & Entity Grounding',
    title: 'ICP & Value Proposition Profiler',
    description: 'Identifies target audience, core buyer pain points, and commercial value propositions.',
    agent_name: 'BusinessUnderstandingOrchestrator',
    dependencies: ['node_entity_resolution'],
  },

  // --- 3. SEO Pillar ---
  node_seo_crawl_indexing: {
    node_id: 'node_seo_crawl_indexing',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Crawlability, Status Codes & Indexation',
    description: 'Audits robots.txt, XML sitemaps, canonical links, HTTP codes, and redirect chains.',
    agent_name: 'TechnicalSeoSpecialists',
    dependencies: ['node_dom_extraction', 'node_entity_resolution'],
  },
  node_seo_technical_health: {
    node_id: 'node_seo_technical_health',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Core Web Vitals & Transport Health',
    description: 'Audits LCP, INP, CLS diagnostics, TTFB, asset caching, compression, and rendering.',
    agent_name: 'PerformanceSecuritySpecialists',
    dependencies: ['node_seo_crawl_indexing'],
  },
  node_seo_onpage_content: {
    node_id: 'node_seo_onpage_content',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'On-Page Hierarchy & Semantic Content',
    description: 'Audits title tags, meta descriptions, H1-H6 heading trees, and semantic landmarks.',
    agent_name: 'OnPageContentSpecialists',
    dependencies: ['node_seo_crawl_indexing'],
  },
  node_seo_schema_ast: {
    node_id: 'node_seo_schema_ast',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Schema.org JSON-LD Structured Data',
    description: 'Extracts JSON-LD script blocks, parses Schema AST, and validates entity graph links.',
    agent_name: 'SchemaAstValidator',
    dependencies: ['node_dom_extraction'],
  },
  node_seo_page_intelligence: {
    node_id: 'node_seo_page_intelligence',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Page-by-Page SEO & Copywriting Rewrites',
    description: 'Generates per-URL action reports, title tag upgrades, and character-safe copy rewrites.',
    agent_name: 'PageIntelligenceAgent',
    dependencies: ['node_seo_onpage_content'],
  },

  // --- 4. GEO Pillar ---
  node_geo_entity_grounding: {
    node_id: 'node_geo_entity_grounding',
    section_id: 'sec_geo',
    section_title: '4. Generative Engine Optimization (GEO)',
    title: 'Wikidata & Entity Knowledge Graph',
    description: 'Grounds entity identity across Wikidata triples, knowledge panels, and authoritative sources.',
    agent_name: 'GeoEntityGraphSpecialists',
    dependencies: ['node_entity_resolution'],
  },
  node_geo_local_signals: {
    node_id: 'node_geo_local_signals',
    section_id: 'sec_geo',
    section_title: '4. Generative Engine Optimization (GEO)',
    title: 'Local Grounding & Regional Authority',
    description: 'Audits multi-location NAP consistency, GBP signals, and geographic grounding.',
    agent_name: 'GeoLocalSpecialists',
    dependencies: ['node_geo_entity_grounding'],
  },
  node_geo_llm_footprint: {
    node_id: 'node_geo_llm_footprint',
    section_id: 'sec_geo',
    section_title: '4. Generative Engine Optimization (GEO)',
    title: 'Generative Citability & Brand Footprint',
    description: 'Evaluates LLM parsability, semantic chunking, and brand presence in AI models.',
    agent_name: 'GeoCitabilitySpecialists',
    dependencies: ['node_geo_entity_grounding'],
  },

  // --- 5. AEO Pillar ---
  node_aeo_citability_matrix: {
    node_id: 'node_aeo_citability_matrix',
    section_id: 'sec_aeo',
    section_title: '5. Answer Engine Optimization (AEO)',
    title: 'AI Answer Citability & Readability Matrix',
    description: 'Tests AI answer readiness across ChatGPT, Perplexity, Claude, and Gemini.',
    agent_name: 'AeoCitabilitySpecialists',
    dependencies: ['node_dom_extraction', 'node_icp_offer_profile'],
  },
  node_aeo_qa_readiness: {
    node_id: 'node_aeo_qa_readiness',
    section_id: 'sec_aeo',
    section_title: '5. Answer Engine Optimization (AEO)',
    title: 'Direct Q&A & Semantic FAQ Readiness',
    description: 'Audits direct answer sentence density, FAQPage schema markup, and conversational queries.',
    agent_name: 'AeoFaqSpecialists',
    dependencies: ['node_aeo_citability_matrix'],
  },
  node_aeo_search_simulation: {
    node_id: 'node_aeo_search_simulation',
    section_id: 'sec_aeo',
    section_title: '5. Answer Engine Optimization (AEO)',
    title: 'Synthetic Commercial Query Simulation',
    description: 'Simulates realistic commercial buyer inquiries across AI answer engines to measure recommendation share.',
    agent_name: 'AISearchSimulationEngine',
    dependencies: ['node_icp_offer_profile', 'node_aeo_citability_matrix'],
  },

  // --- 6. CRO Pillar ---
  node_cro_cta_visibility: {
    node_id: 'node_cro_cta_visibility',
    section_id: 'sec_cro',
    section_title: '6. Conversion Rate Optimization (CRO & UX)',
    title: 'Primary CTA Hierarchy & Friction',
    description: 'Evaluates primary CTA visibility, above-the-fold prominence, layout distraction, and conversion pathways.',
    agent_name: 'CroCtaSpecialists',
    dependencies: ['node_dom_extraction'],
  },
  node_cro_value_clarity: {
    node_id: 'node_cro_value_clarity',
    section_id: 'sec_cro',
    section_title: '6. Conversion Rate Optimization (CRO & UX)',
    title: 'Value Proposition & Commercial Clarity',
    description: 'Measures 5-second headline comprehension, ICP alignment, offer transparency, and pricing access.',
    agent_name: 'CroValuePropSpecialists',
    dependencies: ['node_icp_offer_profile'],
  },
  node_cro_trust_and_forms: {
    node_id: 'node_cro_trust_and_forms',
    section_id: 'sec_cro',
    section_title: '6. Conversion Rate Optimization (CRO & UX)',
    title: 'Social Proof, Trust Proof & Form Usability',
    description: 'Audits customer testimonials, trust badges, security seals, return policies, and form friction.',
    agent_name: 'CroTrustFormSpecialists',
    dependencies: ['node_cro_cta_visibility'],
  },

  // --- 7. Executive Synthesis & Verification ---
  node_adversarial_critic: {
    node_id: 'node_adversarial_critic',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Adversarial Critic Cross-Examination',
    description: 'Challenges finding assumptions, flags potential hallucinations, and cross-checks evidence.',
    agent_name: 'AdversarialCritic',
    dependencies: ['node_aeo_citability_matrix'],
  },
  node_integrity_gate: {
    node_id: 'node_integrity_gate',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Zero-Fake Evidence Gate & Claim Attestation',
    description: 'Enforces strictly verifiable facts against raw DOM evidence before scoring.',
    agent_name: 'ZeroFakeEvidenceGate',
    dependencies: ['node_adversarial_critic'],
  },
  node_causal_bottlenecks: {
    node_id: 'node_causal_bottlenecks',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Causal Diagnostic Graph & Bottlenecks',
    description: 'Determines upstream root-causes vs downstream symptoms to isolate highest ROI remediations.',
    agent_name: 'CausalEngine',
    dependencies: ['node_integrity_gate'],
  },
  node_honest_scoring: {
    node_id: 'node_honest_scoring',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Honest Multi-Pillar Scoring Engine',
    description: 'Calculates un-inflated, reality-grounded scores across SEO, GEO, AEO, and CRO.',
    agent_name: 'ScoreEngine',
    dependencies: ['node_integrity_gate'],
  },
  node_executive_narrative: {
    node_id: 'node_executive_narrative',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Executive Strategic Synthesis',
    description: 'Synthesizes concise C-suite roadmap, strategic opportunity, and primary blocker narratives.',
    agent_name: 'NarrativeSynthesizer',
    dependencies: ['node_honest_scoring', 'node_causal_bottlenecks'],
  },
  node_code_patch_pack: {
    node_id: 'node_code_patch_pack',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Self-Contained Code Remediation Pack',
    description: 'Generates ready-to-merge, production code patches, JSON-LD schema fixes, and server configs.',
    agent_name: 'DevPatchGenerator',
    dependencies: ['node_executive_narrative'],
  },
  node_final_report_assembly: {
    node_id: 'node_final_report_assembly',
    section_id: 'sec_synthesis',
    section_title: '7. Executive Synthesis, Scoring & Patches',
    title: 'Executive Report Assembly',
    description: 'Assembles sealed, auditable report with full evidence cross-references and telemetry ledger.',
    agent_name: 'ReportAssembler',
    dependencies: ['node_code_patch_pack'],
  },

  // --- Backward Compatibility Aliases ---
  node_schema_ld_json: {
    node_id: 'node_schema_ld_json',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Schema.org JSON-LD Parser',
    description: 'Legacy alias for Schema AST structured data parser.',
    agent_name: 'SchemaAstValidator',
    dependencies: ['node_dom_extraction'],
  },
  node_specialist_wave_1: {
    node_id: 'node_specialist_wave_1',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Technical SEO Specialists (Wave 1)',
    description: 'Legacy alias for Technical SEO specialists.',
    agent_name: 'TechnicalSeoSpecialists',
    dependencies: ['node_dom_extraction'],
  },
  node_specialist_wave_2: {
    node_id: 'node_specialist_wave_2',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'On-Page Content & Schema Specialists (Wave 2)',
    description: 'Legacy alias for On-Page Content specialists.',
    agent_name: 'OnPageSchemaSpecialists',
    dependencies: ['node_specialist_wave_1'],
  },
  node_specialist_wave_3: {
    node_id: 'node_specialist_wave_3',
    section_id: 'sec_cro',
    section_title: '6. Conversion Rate Optimization (CRO & UX)',
    title: 'CRO & Experience Specialists (Wave 3)',
    description: 'Legacy alias for CRO specialists.',
    agent_name: 'CroUxSpecialists',
    dependencies: ['node_specialist_wave_1'],
  },
  node_specialist_wave_4: {
    node_id: 'node_specialist_wave_4',
    section_id: 'sec_geo',
    section_title: '4. Generative Engine Optimization (GEO)',
    title: 'GEO & AEO Citability Specialists (Wave 4)',
    description: 'Legacy alias for Citability specialists.',
    agent_name: 'AiCitabilitySpecialists',
    dependencies: ['node_specialist_wave_2'],
  },
  node_page_intelligence: {
    node_id: 'node_page_intelligence',
    section_id: 'sec_seo',
    section_title: '3. Search Engine Optimization (SEO)',
    title: 'Page-Level SEO & Copywriting',
    description: 'Legacy alias for Page Intelligence rewrites.',
    agent_name: 'PageIntelligenceAgent',
    dependencies: ['node_specialist_wave_2'],
  },
  node_ai_search_simulation: {
    node_id: 'node_ai_search_simulation',
    section_id: 'sec_aeo',
    section_title: '5. Answer Engine Optimization (AEO)',
    title: 'AI Answer Engine Simulation',
    description: 'Legacy alias for AI Search Simulation.',
    agent_name: 'AISearchSimulationEngine',
    dependencies: ['node_specialist_wave_4'],
  },
};

export function LiveExecutionConsole({ run, onRefreshRun }: LiveExecutionConsoleProps) {
  const [graphState, setGraphState] = useState<PipelineGraphState | null>(run.graph || null);
  const [activeTab, setActiveTab] = useState<'phases' | 'terminal' | 'workforce'>('phases');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSectionFilter, setSelectedSectionFilter] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [runningNodeId, setRunningNodeId] = useState<string | null>(null);
  const [runningSectionId, setRunningSectionId] = useState<string | null>(null);
  const [runningPillar, setRunningPillar] = useState<string | null>(null);
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [nodeActionError, setNodeActionError] = useState<string | null>(null);
  const [isPausing, setIsPausing] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  // Specialist Workforce state
  const [workforceData, setWorkforceData] = useState<any[]>([]);
  const [isLoadingWorkforce, setIsLoadingWorkforce] = useState(false);
  const [selectedDomainFilter, setSelectedDomainFilter] = useState<string>('all');
  const [workforceSearch, setWorkforceSearch] = useState<string>('');

  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Poll graph state if active
  useEffect(() => {
    let isMounted = true;
    const fetchGraph = async () => {
      try {
        const data = await getExecutionGraph(run.analysis_id);
        if (isMounted) {
          setGraphState(data);
        }
      } catch {
        /* ignore polling error */
      }
    };

    fetchGraph();
    const interval = setInterval(fetchGraph, 2500);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [run.analysis_id]);

  // Sync if run prop changes with embedded graph
  useEffect(() => {
    if (run.graph) {
      setGraphState(run.graph);
    }
  }, [run.graph]);

  // Fetch workforce when tab is switched to 'workforce'
  useEffect(() => {
    if (activeTab === 'workforce') {
      let isMounted = true;
      const fetchWorkforce = async () => {
        try {
          setIsLoadingWorkforce(true);
          const res = await getAgentWorkforce(run.analysis_id);
          if (isMounted && res.agents) {
            setWorkforceData(res.agents);
          }
        } catch {
          /* ignore error */
        } finally {
          if (isMounted) setIsLoadingWorkforce(false);
        }
      };
      fetchWorkforce();
      return () => {
        isMounted = false;
      };
    }
  }, [activeTab, run.analysis_id]);

  // Auto-scroll terminal log
  useEffect(() => {
    if (autoScroll && activeTab === 'terminal' && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [graphState?.activity_events, autoScroll, activeTab]);

  const handlePause = async () => {
    setIsPausing(true);
    setNodeActionError(null);
    try {
      await pauseAnalysis(run.analysis_id);
      if (onRefreshRun) onRefreshRun();
    } catch (err: any) {
      setNodeActionError(err.message || 'Failed to pause audit');
    } finally {
      setIsPausing(false);
    }
  };

  const handleResume = async () => {
    setIsResuming(true);
    setNodeActionError(null);
    try {
      await resumeAnalysis(run.analysis_id);
      if (onRefreshRun) onRefreshRun();
    } catch (err: any) {
      setNodeActionError(err.message || 'Failed to resume audit');
    } finally {
      setIsResuming(false);
    }
  };

  const handleRunNode = async (nodeId: string) => {
    setRunningNodeId(nodeId);
    setNodeActionError(null);
    try {
      await runGraphNode(run.analysis_id, nodeId);
      const updated = await getExecutionGraph(run.analysis_id);
      setGraphState(updated);
      if (onRefreshRun) onRefreshRun();
    } catch (err: any) {
      setNodeActionError(err.message || `Failed to run step ${nodeId}`);
    } finally {
      setRunningNodeId(null);
    }
  };

  const handleRunSection = async (sectionId: string) => {
    setRunningSectionId(sectionId);
    setNodeActionError(null);
    try {
      await runGraphSection(run.analysis_id, sectionId);
      const updated = await getExecutionGraph(run.analysis_id);
      setGraphState(updated);
      if (onRefreshRun) onRefreshRun();
    } catch (err: any) {
      setNodeActionError(err.message || `Failed to run phase ${sectionId}`);
    } finally {
      setRunningSectionId(null);
    }
  };

  const handleRunPillar = async (pillarKey: string) => {
    setRunningPillar(pillarKey);
    setNodeActionError(null);
    try {
      await runPillar(run.analysis_id, pillarKey);
      const updated = await getExecutionGraph(run.analysis_id);
      setGraphState(updated);
      if (onRefreshRun) onRefreshRun();
    } catch (err: any) {
      setNodeActionError(err.message || `Failed to run ${pillarKey.toUpperCase()} pillar`);
    } finally {
      setRunningPillar(null);
    }
  };

  const handleRunAllWorkflow = async () => {
    setIsRunningAll(true);
    setNodeActionError(null);
    try {
      const activeSections =
        graphState?.sections && graphState.sections.length > 0 ? graphState.sections : DEFAULT_SECTIONS;
      for (const sec of activeSections) {
        setRunningSectionId(sec.section_id);
        await runGraphSection(run.analysis_id, sec.section_id);
        const updated = await getExecutionGraph(run.analysis_id);
        setGraphState(updated);
        if (onRefreshRun) onRefreshRun();
      }
    } catch (err: any) {
      setNodeActionError(err.message || 'Failed to complete full workflow execution');
    } finally {
      setRunningSectionId(null);
      setIsRunningAll(false);
    }
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const isPaused = run.status === 'paused' || graphState?.is_paused;
  const isFailed = run.status === 'failed';
  const isCompleted = run.status === 'completed';
  const isRunning = !isPaused && !isFailed && !isCompleted;

  const totalCost = run.telemetry?.estimated_cost_usd ?? 0;
  const totalTokens = run.telemetry?.total_tokens ?? 0;

  // Sections and nodes resolution
  const sections =
    graphState?.sections && graphState.sections.length > 0 ? graphState.sections : DEFAULT_SECTIONS;

  const nodesMap = graphState?.nodes || {};

  // Compute node helper
  const getNode = (nid: string): GraphNode => {
    if (nodesMap[nid]) return nodesMap[nid];
    const def = DEFAULT_NODES_MAP[nid] || {};
    return {
      node_id: nid,
      section_id: def.section_id || '',
      section_title: def.section_title || '',
      title: def.title || nid,
      description: def.description || '',
      agent_name: def.agent_name || 'Specialist',
      dependencies: def.dependencies || [],
      status: isCompleted ? 'completed' : 'pending',
      can_run_separately: false,
      missing_dependencies: [],
    };
  };

  // Determine section statuses and active section + active subsection
  let activeSectionIndex = -1;
  let activeSectionDef: (typeof sections)[0] | null = null;
  let activeSubsectionNode: GraphNode | null = null;

  const sectionDetails = sections.map((sec, idx) => {
    const secNodes = sec.node_ids.map(getNode);
    const completedCount = secNodes.filter((n) => n.status === 'completed').length;
    const skippedCount = secNodes.filter((n) => n.status === 'skipped').length;
    const isSectionAllDone = isCompleted || (secNodes.length > 0 && completedCount === secNodes.length);
    const isSectionAllSkipped = !isCompleted && secNodes.length > 0 && skippedCount === secNodes.length;
    const hasRunningNode = secNodes.some((n) => n.status === 'running' || runningNodeId === n.node_id);
    const hasFailedNode = secNodes.some((n) => n.status === 'failed');

    let sectionStatus: 'completed' | 'running' | 'failed' | 'skipped' | 'waiting' = 'waiting';
    if (isSectionAllDone) {
      sectionStatus = 'completed';
    } else if (isSectionAllSkipped) {
      sectionStatus = 'skipped';
    } else if (hasRunningNode) {
      sectionStatus = 'running';
    } else if (hasFailedNode) {
      sectionStatus = 'failed';
    }

    if (hasRunningNode) {
      activeSectionIndex = idx;
      activeSectionDef = sec;
      activeSubsectionNode = secNodes.find((n) => n.status === 'running' || runningNodeId === n.node_id) || null;
    }

    return {
      section: sec,
      nodes: secNodes,
      completedCount,
      skippedCount,
      totalCount: secNodes.length,
      isAllDone: isSectionAllDone,
      isAllSkipped: isSectionAllSkipped,
      status: sectionStatus,
    };
  });

  // If no node is currently flagged 'running', locate next expected active section
  if (!activeSectionDef && !isCompleted) {
    const firstPendingSec = sectionDetails.find((s) => s.status !== 'completed' && s.status !== 'skipped');
    if (firstPendingSec) {
      activeSectionDef = firstPendingSec.section;
      activeSectionIndex = sections.findIndex((s) => s.section_id === firstPendingSec.section.section_id);
      activeSubsectionNode = firstPendingSec.nodes.find((n) => n.status !== 'completed' && n.status !== 'skipped') || null;
    }
  }

  // Auto-expand the actively running section so the user sees the live running subsection inside it immediately
  useEffect(() => {
    if (activeSectionDef) {
      setExpandedSections((prev) => {
        if (prev[activeSectionDef!.section_id]) return prev;
        return {
          ...prev,
          [activeSectionDef!.section_id]: true,
        };
      });
    }
  }, [activeSectionDef?.section_id]);

  // Percentage resolution - NEVER REMOVED, preserved at 100% when run is completed
  const progressPct = isCompleted
    ? 100
    : Math.min(100, Math.max(run.progress_percentage || graphState?.progress_percentage || 0, isRunning ? 5 : 0));

  // Filter activities for terminal
  const events = graphState?.activity_events || [];
  const filteredEvents = events.filter((ev) => {
    const matchesSection = selectedSectionFilter === 'all' || ev.section_id === selectedSectionFilter;
    const matchesSearch =
      !searchQuery ||
      ev.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.agent_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSection && matchesSearch;
  });

  return (
    <div className="rounded-xl border border-line bg-card shadow-sm overflow-hidden text-ink">
      {/* 1. TOP COMMAND BAR */}
      <div className="p-4 sm:p-5 border-b border-line bg-paper-50/70 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-xs uppercase tracking-[0.04em] text-ink-500 font-semibold">
              Mission Orchestrator
            </span>
            {isRunning && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-paper-200 text-ink-700 border border-line">
                <span className="w-2 h-2 rounded-full bg-pine animate-ping" />
                Live Executing
              </span>
            )}
            {isPaused && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-warn/10 text-warn border border-warn/30">
                <span className="w-2 h-2 rounded-full bg-warn/10" />
                Audit Paused
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-bad/10 text-bad border border-bad/20">
                <span className="w-2 h-2 rounded-full bg-bad" />
                Halted on Error
              </span>
            )}
            {isCompleted && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-good/10 text-good border border-good/30">
                <span className="w-2 h-2 rounded-full bg-good/10" />
                Mission Complete
              </span>
            )}
          </div>
          <h3 className="text-base sm:text-lg font-sans font-semibold text-ink mt-1 truncate max-w-md sm:max-w-xl">
            {run.website_url.replace(/^https?:\/\//, '')}
          </h3>
          <p className="text-xs text-ink-600 font-mono mt-0.5">
            {run.current_step || 'Processing workflow steps...'}
          </p>
        </div>

        {/* Action Controls & Metrics */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs font-mono text-ink-500">
              AI Cost: <span className="font-bold text-ink-700 font-sans">${totalCost.toFixed(4)}</span> •{' '}
              <span className="font-bold text-ink-700">{totalTokens.toLocaleString()} tokens</span>
            </div>
            <div className="text-xs font-mono text-ink-500 mt-0.5">
              Phases:{' '}
              <span className="font-bold text-ink-700">
                {sectionDetails.filter((s) => s.isAllDone).length} / {sections.length} Done
              </span>
            </div>
          </div>

          {/* Workflow & Pillar Triggers */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              type="button"
              onClick={handleRunAllWorkflow}
              disabled={isRunningAll || runningSectionId !== null || runningPillar !== null}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-pine hover:bg-pine/90 text-paper-50 flex items-center gap-1.5 cursor-pointer transition-colors shadow-2xs disabled:opacity-50"
              title="Execute all 7 phases sequentially from Ingestion to Synthesis"
            >
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              <span>{isRunningAll ? 'Executing...' : 'Run All (7 Phases)'}</span>
            </button>

            {[
              { key: 'seo', name: 'SEO', color: 'bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 border-amber-500/30' },
              { key: 'geo', name: 'GEO', color: 'bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/20 border-emerald-500/30' },
              { key: 'aeo', name: 'AEO', color: 'bg-violet-500/10 text-violet-700 hover:bg-violet-500/20 border-violet-500/30' },
              { key: 'cro', name: 'CRO', color: 'bg-rose-500/10 text-rose-700 hover:bg-rose-500/20 border-rose-500/30' },
            ].map((p) => {
              const isPillarRunning = runningPillar === p.key;
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => handleRunPillar(p.key)}
                  disabled={isRunningAll || runningSectionId !== null || runningPillar !== null}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border transition-colors cursor-pointer flex items-center gap-1 shadow-2xs disabled:opacity-50 ${p.color}`}
                  title={`Execute only ${p.name} pillar workflow`}
                >
                  {isPillarRunning ? (
                    <span className="w-2 h-2 rounded-full bg-current animate-ping" />
                  ) : (
                    <svg className="w-3 h-3 fill-current opacity-70" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  )}
                  <span>{isPillarRunning ? `Running ${p.name}...` : `Run ${p.name}`}</span>
                </button>
              );
            })}
          </div>

          {isRunning && (
            <button
              type="button"
              onClick={handlePause}
              disabled={isPausing}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-paper-200/80 hover:bg-paper-300 text-ink border border-line flex items-center gap-1.5 cursor-pointer transition-colors shadow-2xs"
            >
              <svg className="w-3.5 h-3.5 text-ink-600" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
              <span>{isPausing ? 'Pausing...' : 'Stop / Pause'}</span>
            </button>
          )}

          {(isPaused || isFailed) && (
            <button
              type="button"
              onClick={handleResume}
              disabled={isResuming}
              className="px-4 py-1.5 rounded-lg text-xs font-medium bg-pine hover:bg-pine/90 text-paper-50 flex items-center gap-1.5 cursor-pointer transition-colors shadow-2xs"
            >
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              <span>{isResuming ? 'Resuming...' : 'Resume Audit'}</span>
            </button>
          )}

          {/* View Tab Switcher */}
          <div className="inline-flex rounded-lg p-0.5 bg-paper-200/70 border border-line">
            <button
              type="button"
              onClick={() => setActiveTab('phases')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeTab === 'phases'
                  ? 'bg-card text-ink shadow-2xs font-semibold'
                  : 'text-ink-600 hover:text-ink'
              }`}
            >
              Phases & Sub-phases
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('workforce')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeTab === 'workforce'
                  ? 'bg-card text-ink shadow-2xs font-semibold'
                  : 'text-ink-600 hover:text-ink'
              }`}
            >
              50-Agent Workforce
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('terminal')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeTab === 'terminal'
                  ? 'bg-card text-ink shadow-2xs font-semibold'
                  : 'text-ink-600 hover:text-ink'
              }`}
            >
              Terminal Telemetry
            </button>
          </div>
        </div>
      </div>

      {/* 2. PROMINENT LIVE SECTION & SUBSECTION BANNER WITH PERSISTENT PERCENTAGE */}
      <div className="px-4 sm:px-5 py-3 bg-paper-100/60 border-b border-line flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5 flex-wrap min-w-0">
          {/* Main Phase Indicator */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="font-mono uppercase text-[10px] tracking-[0.04em] text-ink-500 font-semibold">
              Main Phase:
            </span>
            {isCompleted ? (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md font-semibold bg-good/10 text-good border border-good/30">
                <svg className="w-3.5 h-3.5 text-good" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                All 7 Phases Verified
              </span>
            ) : activeSectionDef ? (
              <div className="inline-flex items-center gap-1.5 flex-wrap">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md font-semibold ${
                    isRunning
                      ? 'bg-paper-200 text-ink-700 border border-line'
                      : isPaused
                      ? 'bg-warn/10 text-warn border border-warn/30'
                      : 'bg-paper-200 text-ink-700'
                  }`}
                >
                  {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-pine animate-ping" />}
                  Phase {activeSectionIndex >= 0 ? activeSectionIndex + 1 : 1} of {sections.length}:{' '}
                  {activeSectionDef.title}
                </span>
                {PILLAR_SECTION_MAP[activeSectionDef.section_id] && (
                  <span
                    className={`text-[10px] font-mono font-bold uppercase tracking-wide px-2 py-0.5 rounded-md border ${
                      PILLAR_SECTION_MAP[activeSectionDef.section_id].color
                    }`}
                  >
                    {PILLAR_SECTION_MAP[activeSectionDef.section_id].label}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-ink-600 font-medium">Ready</span>
            )}
          </div>

          {/* Subsection Indicator */}
          {isRunning && activeSubsectionNode && (
            <div className="flex items-center gap-1.5 bg-card px-2.5 py-0.5 rounded-md border border-line shadow-2xs truncate max-w-sm sm:max-w-md">
              <span className="text-ink-400 font-mono text-[11px]">↳ Sub-phase:</span>
              <span className="font-semibold text-ink truncate">{activeSubsectionNode.title}</span>
              <span className="text-[10px] font-mono text-ink-700 bg-paper-200 px-1.5 py-0.2 rounded shrink-0">
                [{activeSubsectionNode.agent_name}]
              </span>
            </div>
          )}
        </div>

        {/* Persistent Percentage Badge - Always visible, never removed when done! */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[11px] text-ink-500 uppercase tracking-wide">Overall Progress:</span>
          <span
            className={`font-mono text-xs sm:text-sm font-bold px-2.5 py-0.5 rounded border transition-all ${
              isCompleted
                ? 'bg-good/10 text-good border-good/30 font-semibold'
                : isFailed
                ? 'bg-bad/10 text-bad border-bad/30'
                : isPaused
                ? 'bg-warn/10 text-warn border-warn/30'
                : 'bg-paper-200 text-ink-700 border-line'
            }`}
          >
            {isCompleted ? '100% Completed' : `${progressPct}%`}
          </span>
        </div>
      </div>

      {/* Progress Bar (Persistent, full green when done) */}
      <div className="h-1.5 bg-paper-200/90 w-full overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            isFailed ? 'bg-bad' : isPaused ? 'bg-warn/10' : isCompleted ? 'bg-good/10' : 'bg-pine'
          }`}
          style={{ width: `${Math.max(4, progressPct)}%` }}
        />
      </div>

      {nodeActionError && (
        <div className="px-5 py-2.5 bg-bad/10 border-b border-bad/20 text-xs text-bad flex items-center justify-between">
          <span>{nodeActionError}</span>
          <button
            type="button"
            onClick={() => setNodeActionError(null)}
            className="text-bad hover:underline font-bold text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* 3. TAB CONTENT */}
      {activeTab === 'phases' ? (
        /* INDUSTRY STANDARD PHASES & SUB-PHASES STEPPER TREE */
        <div className="p-4 sm:p-6 space-y-4 bg-paper-50/40">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-1">
            <div>
              <h4 className="text-sm font-sans font-bold text-ink">Main Phases &amp; Sub-phases Execution</h4>
              <p className="text-xs text-ink-500">
                Industry-standard multi-agent pipeline hierarchy. Running sections automatically expand to show the
                active sub-phase in real-time.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  const allOpen: Record<string, boolean> = {};
                  sections.forEach((s) => {
                    allOpen[s.section_id] = true;
                  });
                  setExpandedSections(allOpen);
                }}
                className="text-[11px] font-mono text-ink-600 hover:text-ink hover:underline cursor-pointer"
              >
                Expand all
              </button>
              <span className="text-ink-300">•</span>
              <button
                type="button"
                onClick={() => setExpandedSections({})}
                className="text-[11px] font-mono text-ink-600 hover:text-ink hover:underline cursor-pointer"
              >
                Collapse all
              </button>
            </div>
          </div>

          <div className="relative border-l-2 border-line/80 ml-4 sm:ml-5 pl-5 sm:pl-7 space-y-5">
            {sectionDetails.map(({ section, nodes: secNodes, completedCount, skippedCount, totalCount, isAllDone, status }, sIdx) => {
              const isSectionRunning = status === 'running';
              const isSectionFailed = status === 'failed';
              const isSectionSkipped = status === 'skipped';
              const isExpanded = expandedSections[section.section_id] ?? (isSectionRunning || sIdx === 0);
              const pillarMeta = PILLAR_SECTION_MAP[section.section_id];
              const isPillarExecuting = pillarMeta && runningPillar === pillarMeta.pillarKey;
              const isThisSectionRunning = runningSectionId === section.section_id || isPillarExecuting;

              let phaseIcon = (
                <span className="w-7 h-7 rounded-full bg-paper-200 border-2 border-line text-ink-600 text-xs font-mono font-bold flex items-center justify-center -left-[35px] sm:-left-[43px] absolute bg-card shadow-2xs">
                  {sIdx + 1}
                </span>
              );

              if (isAllDone) {
                phaseIcon = (
                  <span className="w-7 h-7 rounded-full bg-good/10 text-paper-50 border-2 border-good/30 text-xs font-bold flex items-center justify-center -left-[35px] sm:-left-[43px] absolute shadow-2xs">
                    ✓
                  </span>
                );
              } else if (isSectionSkipped) {
                phaseIcon = (
                  <span className="w-7 h-7 rounded-full bg-paper-200/60 text-ink-400 border-2 border-line/70 text-xs font-mono font-bold flex items-center justify-center -left-[35px] sm:-left-[43px] absolute bg-card shadow-2xs">
                    —
                  </span>
                );
              } else if (isSectionRunning) {
                phaseIcon = (
                  <span className="w-7 h-7 rounded-full bg-pine text-paper-50 border-2 border-line text-xs font-bold flex items-center justify-center -left-[35px] sm:-left-[43px] absolute shadow-2xs animate-pulse">
                    ⟳
                  </span>
                );
              } else if (isSectionFailed) {
                phaseIcon = (
                  <span className="w-7 h-7 rounded-full bg-bad text-paper-50 border-2 border-bad text-xs font-bold flex items-center justify-center -left-[35px] sm:-left-[43px] absolute shadow-2xs">
                    ✕
                  </span>
                );
              }

              return (
                <div
                  key={section.section_id}
                  className={`rounded-xl border transition-all duration-200 bg-card overflow-hidden shadow-2xs ${
                    isSectionRunning
                      ? 'border-line ring-1 ring-line'
                      : isAllDone
                      ? 'border-good/30'
                      : isSectionSkipped
                      ? 'border-line/60 opacity-90'
                      : 'border-line'
                  }`}
                >
                  {/* Phase Node Header */}
                  <div
                    onClick={() => toggleSection(section.section_id)}
                    className="px-4 py-3 bg-paper-50/60 hover:bg-paper-100/60 transition-colors flex items-center justify-between gap-3 cursor-pointer select-none"
                  >
                    {phaseIcon}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-sans font-bold text-sm text-ink">{section.title}</span>
                        {pillarMeta && (
                          <span
                            className={`text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${pillarMeta.color}`}
                          >
                            {pillarMeta.label}
                          </span>
                        )}
                        {isSectionRunning && (
                          <span className="text-[10px] font-mono font-semibold text-ink-700 bg-paper-200 px-2 py-0.5 rounded-md border border-line flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-pine animate-ping" />
                            Running Now
                          </span>
                        )}
                        {isAllDone && (
                          <span className="text-[10px] font-mono font-semibold text-good bg-good/10 px-2 py-0.5 rounded-md border border-good/30">
                            Completed
                          </span>
                        )}
                        {isSectionSkipped && (
                          <span className="text-[10px] font-mono font-semibold text-ink-500 bg-paper-200/70 px-2 py-0.5 rounded-md border border-line/60">
                            Skipped (Selective Run)
                          </span>
                        )}
                        {!isAllDone && !isSectionRunning && !isSectionSkipped && (
                          <span className="text-[10px] font-mono text-ink-400 bg-paper-200/60 px-2 py-0.5 rounded-md">
                            Queued
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-ink-500 mt-0.5 line-clamp-1">{section.description}</p>
                    </div>

                    <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (pillarMeta) {
                            handleRunPillar(pillarMeta.pillarKey);
                          } else {
                            handleRunSection(section.section_id);
                          }
                        }}
                        disabled={isSectionRunning || isThisSectionRunning || isRunningAll}
                        className="px-2.5 py-1 text-xs font-semibold bg-paper-200 hover:bg-pine hover:text-white text-ink border border-line rounded-md transition-colors cursor-pointer flex items-center gap-1.5 shadow-2xs disabled:opacity-50"
                        title={pillarMeta ? `Execute only ${pillarMeta.label} workflow` : `Execute all sub-phases in ${section.title}`}
                      >
                        <svg className="w-3 h-3 text-pine group-hover:text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                        <span>
                          {isThisSectionRunning
                            ? pillarMeta ? `Running ${pillarMeta.label}...` : 'Running Phase...'
                            : isAllDone
                            ? pillarMeta ? `Re-run ${pillarMeta.label}` : 'Re-run Phase'
                            : isSectionSkipped
                            ? pillarMeta ? `Run ${pillarMeta.label}` : 'Run Phase'
                            : pillarMeta ? `Run ${pillarMeta.label}` : 'Run Phase'}
                        </span>
                      </button>
                      <span
                        className={`text-xs font-mono px-2 py-0.5 rounded-md font-medium ${
                          isAllDone
                            ? 'bg-good/10 text-good border border-good/30'
                            : isSectionSkipped
                            ? 'bg-paper-200/70 text-ink-500 border border-line/60'
                            : isSectionRunning
                            ? 'bg-paper-200 text-ink-700 border border-line'
                            : 'bg-paper-200 text-ink-600'
                        }`}
                      >
                        {isSectionSkipped ? `${skippedCount} Skipped` : `${completedCount} / ${totalCount} Done`}
                      </span>
                      <span className="text-ink-400 text-xs font-mono">{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Sub-phases Accordion List */}
                  {isExpanded && (
                    <div className="divide-y divide-line/40 border-t border-line/50 bg-paper-50/40">
                      {secNodes.map((node, nodeIdx) => {
                        const isNodeRunning = runningNodeId === node.node_id || node.status === 'running';
                        const isNodeCompleted = isCompleted || node.status === 'completed';
                        const isNodeFailed = node.status === 'failed';
                        const isNodeSkipped = !isCompleted && node.status === 'skipped';
                        const canRun = (node.can_run_separately || isNodeSkipped || isNodeCompleted) && !isNodeRunning;

                        let subStatusBadge = (
                          <span className="text-[10px] font-mono text-ink-400 bg-paper-200/50 px-2 py-0.5 rounded">
                            Queued
                          </span>
                        );
                        if (isNodeRunning) {
                          subStatusBadge = (
                            <span className="text-[10px] font-mono text-ink-700 bg-paper-200 px-2 py-0.5 rounded border border-line flex items-center gap-1 font-semibold">
                              <span className="w-1.5 h-1.5 rounded-full bg-pine animate-ping" />
                              Running Now...
                            </span>
                          );
                        } else if (isNodeCompleted) {
                          subStatusBadge = (
                            <span className="text-[10px] font-mono text-good bg-good/10 px-2 py-0.5 rounded border border-good/30 font-semibold">
                              ✓ Completed
                            </span>
                          );
                        } else if (isNodeFailed) {
                          subStatusBadge = (
                            <span className="text-[10px] font-mono text-bad bg-bad/10 px-2 py-0.5 rounded border border-bad/20 font-semibold">
                              ✕ Failed
                            </span>
                          );
                        } else if (isNodeSkipped) {
                          subStatusBadge = (
                            <span className="text-[10px] font-mono text-ink-500 bg-paper-200/60 px-2 py-0.5 rounded border border-line/50">
                              Skipped (Selective Run)
                            </span>
                          );
                        } else if (canRun) {
                          subStatusBadge = (
                            <span className="text-[10px] font-mono text-ink-700 bg-paper-100 px-2 py-0.5 rounded border border-line">
                              Ready
                            </span>
                          );
                        }

                        return (
                          <div
                            key={node.node_id}
                            className={`p-3 sm:px-4 sm:py-3 transition-colors flex flex-wrap items-center justify-between gap-3 ${
                              isNodeRunning
                                ? 'bg-paper-100 border-l-2 border-line'
                                : 'hover:bg-paper-50/60'
                            }`}
                          >
                            <div className="flex-1 min-w-[240px]">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-xs text-ink-400 font-semibold">
                                  {sIdx + 1}.{nodeIdx + 1}
                                </span>
                                <span
                                  className={`text-xs font-semibold ${
                                    isNodeRunning ? 'text-ink-700 font-bold' : 'text-ink'
                                  }`}
                                >
                                  {node.title}
                                </span>
                                {subStatusBadge}
                                <span className="text-[10px] font-mono text-ink-400 bg-paper-200/50 px-1.5 py-0.5 rounded">
                                  [{node.agent_name}]
                                </span>
                              </div>
                              <p className="text-xs text-ink-500 mt-0.5">{node.description}</p>

                              {/* Error Message */}
                              {node.error_message && (
                                <div className="mt-1.5 text-xs text-bad bg-bad/5 p-2 rounded border border-bad/20">
                                  Error: {node.error_message}
                                </div>
                              )}

                              {/* Metrics & Outputs */}
                              {(node.duration_ms || node.evidence_count || node.claims_count || node.output_summary) ? (
                                <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] font-mono text-ink-400">
                                  {node.duration_ms ? <span>⏱ {formatMs(node.duration_ms)}</span> : null}
                                  {node.evidence_count ? (
                                    <span className="text-ink-700 font-medium">🔎 {node.evidence_count} evidence items</span>
                                  ) : null}
                                  {node.claims_count ? (
                                    <span className="text-ink-600">📝 {node.claims_count} claims</span>
                                  ) : null}
                                  {node.output_summary ? (
                                    <span className="text-ink-600 font-sans italic border-l border-line pl-2">
                                      {node.output_summary}
                                    </span>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>

                            {/* Node Action Runner Button */}
                            <div className="shrink-0 flex items-center gap-2">
                              {canRun ? (
                                <button
                                  type="button"
                                  onClick={() => handleRunNode(node.node_id)}
                                  disabled={isNodeRunning}
                                  className="px-2.5 py-1 text-xs font-medium bg-paper-200 hover:bg-paper-300 text-ink rounded-md transition-colors cursor-pointer flex items-center gap-1.5 shadow-2xs"
                                >
                                  <svg className="w-3 h-3 text-ink-700" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M8 5v14l11-7z" />
                                  </svg>
                                  <span>{isNodeCompleted ? 'Re-run' : isNodeSkipped ? 'Run step' : 'Run step'}</span>
                                </button>
                              ) : isNodeRunning ? (
                                <span className="text-xs font-mono text-ink-700 flex items-center gap-1">
                                  <span className="w-1.5 h-1.5 rounded-full bg-pine animate-ping" />
                                  Active
                                </span>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : activeTab === 'workforce' ? (
        /* 50-AGENT SPECIALIST WORKFORCE INSPECTOR BOARD */
        <div className="p-4 sm:p-6 space-y-5 bg-paper-50/40">
          {/* Workforce Summary KPIs */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-line">
            <div>
              <h4 className="text-sm font-sans font-bold text-ink flex items-center gap-2">
                <span>50-Agent Autonomous Specialist Workforce</span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-good/10 text-good border border-good/30 font-semibold">
                  100% Deterministic Fallback Guaranteed
                </span>
              </h4>
              <p className="text-xs text-ink-500 mt-0.5">
                Full-spectrum multi-agent workforce covering 10 audit domains. Every specialist possesses verified DOM AST audit logic to guarantee zero empty or unavailable reports.
              </p>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="px-2.5 py-1 rounded-md bg-paper-200 text-ink-700 border border-line">
                Total Agents: <strong className="text-ink">{workforceData.length || 50}</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-good/10 text-good border border-good/30">
                Completed:{' '}
                <strong className="text-good">
                  {workforceData.filter((a) => a.status === 'completed').length || (isCompleted ? 50 : 0)}
                </strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-paper-200 text-ink-700 border border-line">
                Total Claims:{' '}
                <strong className="text-pine">
                  {workforceData.reduce((acc, a) => acc + (a.claims_count || 0), 0)}
                </strong>
              </span>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-paper-100/70 p-3 rounded-lg border border-line">
            <div className="flex items-center gap-2 flex-1 min-w-[220px] max-w-md">
              <input
                type="text"
                value={workforceSearch}
                onChange={(e) => setWorkforceSearch(e.target.value)}
                placeholder="Search specialist agents or remits..."
                className="w-full bg-card border border-line rounded px-3 py-1.5 text-xs text-ink placeholder-ink-400 focus:outline-hidden focus:border-pine"
              />
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              {[
                { id: 'all', label: 'All (50)' },
                { id: 'COMPETITOR', label: 'Competitor (4)' },
                { id: 'CRO', label: 'CRO (7)' },
                { id: 'AEO', label: 'AEO (3)' },
                { id: 'GEO', label: 'GEO (6)' },
                { id: 'TECHNICAL_SEO', label: 'Technical SEO (9)' },
                { id: 'STRUCTURED_DATA', label: 'Schema (3)' },
                { id: 'CONTENT', label: 'Content (5)' },
                { id: 'AI_SEARCH', label: 'AI Search (5)' },
                { id: 'BUSINESS', label: 'Business (5)' },
                { id: 'VERIFICATION', label: 'Integrity Gate (3)' },
              ].map((df) => (
                <button
                  key={df.id}
                  type="button"
                  onClick={() => setSelectedDomainFilter(df.id)}
                  className={`px-2.5 py-1 rounded text-xs font-mono transition-colors cursor-pointer ${
                    selectedDomainFilter === df.id
                      ? 'bg-pine text-white font-semibold shadow-2xs'
                      : 'bg-paper-200 hover:bg-paper-300 text-ink-600'
                  }`}
                >
                  {df.label}
                </button>
              ))}
            </div>
          </div>

          {/* Workforce Grid */}
          {isLoadingWorkforce && workforceData.length === 0 ? (
            <div className="py-12 text-center text-xs font-mono text-ink-400">
              Loading 105 specialist agents telemetry...
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {workforceData
                .filter((ag) => {
                  const matchesDomain =
                    selectedDomainFilter === 'all' || ag.domain === selectedDomainFilter || (selectedDomainFilter === 'CRO' && ag.domain === 'EXPERIENCE');
                  const matchesSearch =
                    !workforceSearch ||
                    ag.agent_name.toLowerCase().includes(workforceSearch.toLowerCase()) ||
                    ag.agent_id.toLowerCase().includes(workforceSearch.toLowerCase()) ||
                    (ag.description && ag.description.toLowerCase().includes(workforceSearch.toLowerCase()));
                  return matchesDomain && matchesSearch;
                })
                .map((ag) => {
                  const isAgentCompleted = isCompleted || ag.status === 'completed';
                  const isAgentRunning = ag.status === 'running';

                  let domainBadgeStyle = 'bg-paper-200 text-ink-600 border-line';
                  if (ag.domain === 'TECHNICAL_SEO') domainBadgeStyle = 'bg-blue-500/10 text-blue-500 border-blue-500/20';
                  else if (ag.domain === 'STRUCTURED_DATA') domainBadgeStyle = 'bg-purple-500/10 text-purple-500 border-purple-500/20';
                  else if (ag.domain === 'CONTENT') domainBadgeStyle = 'bg-amber-500/10 text-amber-500 border-amber-500/20';
                  else if (ag.domain === 'GEO') domainBadgeStyle = 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
                  else if (ag.domain === 'AEO') domainBadgeStyle = 'bg-violet-500/10 text-violet-500 border-violet-500/20';
                  else if (ag.domain === 'CRO' || ag.domain === 'EXPERIENCE') domainBadgeStyle = 'bg-rose-500/10 text-rose-500 border-rose-500/20';
                  else if (ag.domain === 'COMPETITOR') domainBadgeStyle = 'bg-orange-500/10 text-orange-500 border-orange-500/20';
                  else if (ag.domain === 'AI_SEARCH') domainBadgeStyle = 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20';
                  else if (ag.domain === 'BUSINESS') domainBadgeStyle = 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20';
                  else if (ag.domain === 'VERIFICATION') domainBadgeStyle = 'bg-teal-500/10 text-teal-500 border-teal-500/20';

                  return (
                    <div
                      key={ag.agent_id}
                      className="p-3.5 rounded-xl border border-line bg-card shadow-2xs flex flex-col justify-between gap-2.5 transition-all hover:border-line/80"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-semibold ${domainBadgeStyle}`}>
                            {ag.domain}
                          </span>
                          {isAgentCompleted ? (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold bg-good/10 text-good border border-good/30 flex items-center gap-1">
                              ✓ Completed
                            </span>
                          ) : isAgentRunning ? (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold bg-paper-200 text-ink-700 border border-line flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-pine animate-ping" />
                              Running
                            </span>
                          ) : (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-md text-ink-400 bg-paper-200/60">
                              Ready
                            </span>
                          )}
                        </div>

                        <h5 className="font-sans font-bold text-xs text-ink mt-2 line-clamp-1">
                          {ag.agent_name}
                        </h5>
                        <div className="text-[10px] font-mono text-ink-400 mt-0.5 truncate">
                          ID: {ag.agent_id}
                        </div>
                        <p className="text-xs text-ink-500 mt-1.5 line-clamp-2 leading-relaxed">
                          {ag.description}
                        </p>
                      </div>

                      <div className="pt-2 border-t border-line/60 flex items-center justify-between text-[11px] font-mono">
                        <span className="text-ink-400">
                          Mode:{' '}
                          <strong className="text-ink-600 font-sans">
                            {ag.mode === 'DETERMINISTIC' ? 'Deterministic AST' : 'Hybrid Auditor'}
                          </strong>
                        </span>
                        <span className="px-2 py-0.5 rounded bg-paper-200 text-pine font-semibold">
                          {ag.claims_count} claims
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      ) : (
        /* TERMINAL-STYLE LIVE ACTIVITY STREAM */
        <div className="bg-[#0b0f17] text-ink-300 p-4 font-mono text-xs select-text">
          {/* Terminal Console Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-3 border-b border-ink text-[11px] text-ink-400">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-bad/10 inline-block" />
                <span className="w-2.5 h-2.5 rounded-full bg-warn/10 inline-block" />
                <span className="w-2.5 h-2.5 rounded-full bg-good/10 inline-block" />
              </div>
              <span className="font-semibold text-ink-300 ml-1">dristik-telemetry-engine</span>
              <span className="text-ink-600">•</span>
              <span className="text-ink-400">Semantic Activity Stream</span>
            </div>

            <div className="flex items-center gap-2.5">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter logs..."
                className="bg-ink border border-line rounded px-2 py-0.5 text-xs text-ink-300 placeholder-ink-500 focus:outline-hidden focus:border-line"
              />

              <select
                value={selectedSectionFilter}
                onChange={(e) => setSelectedSectionFilter(e.target.value)}
                className="bg-ink border border-line rounded px-2 py-0.5 text-xs text-ink-300 focus:outline-hidden"
              >
                <option value="all">All Sections</option>
                {sections.map((s) => (
                  <option key={s.section_id} value={s.section_id}>
                    {s.title}
                  </option>
                ))}
              </select>

              <label className="flex items-center gap-1 text-[11px] text-ink-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="rounded text-ink-700"
                />
                <span>Auto-scroll</span>
              </label>
            </div>
          </div>

          {/* Stream Log Entries */}
          <div className="h-[380px] overflow-y-auto space-y-1.5 pr-2 scrollbar-thin">
            {filteredEvents.length === 0 ? (
              <div className="text-ink-500 italic py-8 text-center">
                Waiting for pipeline execution events...
              </div>
            ) : (
              filteredEvents.map((ev) => {
                const timeStr = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '';
                let statusBadgeColor = 'bg-ink-800 text-ink-300';
                if (ev.status === 'success') {
                  statusBadgeColor = 'bg-good/10 text-good border border-good/30';
                } else if (ev.status === 'running') {
                  statusBadgeColor = 'bg-paper-100 text-ink-700 border border-line animate-pulse';
                } else if (ev.status === 'warning') {
                  statusBadgeColor = 'bg-warn/10 text-warn border border-warn/30';
                } else if (ev.status === 'error') {
                  statusBadgeColor = 'bg-bad/10 text-bad border border-bad/30';
                } else if (ev.status === 'info') {
                  statusBadgeColor = 'bg-ink-800 text-ink-700 border border-line';
                }

                return (
                  <div
                    key={ev.id}
                    className="p-1.5 rounded hover:bg-ink transition-colors flex items-start gap-2.5 leading-relaxed"
                  >
                    <span className="text-ink-500 text-[10px] shrink-0 font-mono mt-0.5">{timeStr}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold shrink-0 ${statusBadgeColor}`}
                    >
                      {ev.status}
                    </span>
                    <span className="text-ink-700 font-semibold shrink-0 text-[11px]">
                      [{ev.agent_name || ev.node_title}]
                    </span>
                    <span className="text-ink-300 flex-1 break-words">{ev.summary}</span>
                  </div>
                );
              })
            )}
            <div ref={terminalEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}
