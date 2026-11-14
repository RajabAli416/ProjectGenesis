import type { Provenance, ProvenanceClass } from '@/domain';
import type { Tone } from '@/lib/status';
import { Tag } from '@/components/ui';
import { fmtPct } from '@/lib/format';
import s from './ObservatoryPage.module.css';

const LABEL: Record<ProvenanceClass, string> = {
  'prompt-exposed': 'prompt-exposed',
  'evidence-linked': 'evidence-linked',
  'model-originated': 'model-originated',
  operator: 'operator',
};

const TONE: Record<ProvenanceClass, Tone | undefined> = {
  'prompt-exposed': 'attn',
  'evidence-linked': 'live',
  'model-originated': undefined,
  operator: 'sel',
};

const TITLE: Record<ProvenanceClass, string> = {
  'prompt-exposed': 'The claim reuses vocabulary the agent had already seen in prompts or messages; it is not an independent discovery.',
  'evidence-linked': 'The claim is tied to mechanics-verified measurements.',
  'model-originated': 'The claim was produced by the model without verified evidence; treat as a conjecture.',
  operator: 'Entered by the operator.',
};

/** Compact classification chip used in lists. */
export function ProvenanceTag({ provenance }: { provenance: Provenance | undefined }) {
  if (!provenance) return null;
  return (
    <Tag tone={TONE[provenance.classification]} title={TITLE[provenance.classification]}>
      {LABEL[provenance.classification]}
    </Tag>
  );
}

/** Full provenance block for the detail header. */
export function ProvenanceNote({ provenance, existential }: { provenance: Provenance | undefined; existential?: boolean }) {
  if (!provenance && !existential) return null;
  return (
    <div className={s.provenance}>
      <div className={s.provenanceHead}>
        <span className="caps">Provenance</span>
        <ProvenanceTag provenance={provenance} />
        {existential && (
          <Tag tone="attn" title="The claim concerns the nature of the world itself — simulation, creator or boundary. These are the claims most likely to be prompt contamination, so exposure is checked strictly.">
            existential
          </Tag>
        )}
        {provenance && <span className="faint mono">{fmtPct(provenance.verifiedEvidenceRatio)} of evidence mechanics-verified</span>}
      </div>
      {provenance?.note && <p className={s.provenanceNote}>{provenance.note}</p>}
      {provenance && provenance.promptExposedTerms.length > 0 && (
        <div className={s.provenanceTerms}>
          <span className="faint">Exposed terms:</span>
          {provenance.promptExposedTerms.map((t) => (
            <span key={t} className={s.provenanceTerm}>
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
