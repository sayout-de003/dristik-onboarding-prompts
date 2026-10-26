import React from 'react';
import { ExecutiveReport } from '../types';
import { VerificationProofCard } from './VerificationProofCard';
import { RegressionDetectionView } from './RegressionDetectionView';
import { ComparativeEvidenceMatrix } from './ComparativeEvidenceMatrix';
import { Card } from './ui';
import { ShieldCheck, RefreshCw, History } from 'lucide-react';

interface VerificationWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
}

export function VerificationWorkspaceView({ report, analysisId }: VerificationWorkspaceViewProps) {
  const verifiedFindings = (report.findings || []).filter(
    (f) => f.remediation_verification || f.verification_status === 'VERIFIED'
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-line pb-4">
        <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-700 font-bold block">
          Fix validation
        </span>
        <h2 className="font-sans text-3xl text-ink font-semibold">Verify changes</h2>
        <p className="text-xs text-ink-500 mt-1">
          Re-check the affected pages, compare the new evidence with the previous result, and record what was verified. A generated patch is not proof that a change shipped or worked.
        </p>
      </div>

      {/* Verification Pipeline Stages */}
      <Card className="p-5 space-y-4">
        <h3 className="font-sans text-lg text-ink font-semibold">How verification works</h3>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
          {[
            { step: '1. FIX', desc: 'Apply the proposed change' },
            { step: '2. RECHECK PAGE', desc: 'Fetch the affected page again' },
            { step: '3. TEST', desc: 'Repeat the relevant check' },
            { step: '4. COMPARE', desc: 'Compare before and after evidence' },
            { step: '5. RECORD', desc: 'Save the verification result' },
          ].map((s, i) => (
            <div key={i} className="p-3 rounded bg-paper-50 border border-line space-y-1">
              <span className="font-mono font-bold text-ink-700 text-[11px] block">{s.step}</span>
              <p className="text-ink-600 text-[11px]">{s.desc}</p>
              <span className="text-[10px] text-good font-semibold flex items-center gap-1 pt-1">
                <span aria-hidden="true">→</span> Workflow step
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Regression Detection */}
      {report.regression_report && (
        <RegressionDetectionView report={report} />
      )}

      {/* Comparative Benchmark — Pending Competitor Crawl */}
      <ComparativeEvidenceMatrix
        targetDomain={report.domain}
        manifest={report.crawl_manifest}
        pages={report.crawl_manifest?.pages}
        report={report}
      />

      {/* Sample Verified Evidence Cards */}
      {verifiedFindings.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-sans text-lg text-ink font-semibold">Certified Verification Proofs</h3>
          <div className="space-y-4">
            {verifiedFindings.slice(0, 3).map((f) => (
              <VerificationProofCard key={f.finding_id} finding={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
