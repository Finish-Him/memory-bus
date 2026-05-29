/**
 * Memory Bus Client — TypeScript client for Atlas v2 integration.
 *
 * Usage:
 *   import { MemoryBusClient } from './memory-bus-client';
 *   const bus = new MemoryBusClient({ baseUrl, apiKey });
 *   const results = await bus.search('atlas', 'Quantos monitores temos?');
 */

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
  lexical_score?: number;
  rrf_score?: number;
  metadata: Record<string, unknown>;
  sensitivity: string;
}

export interface SearchResponse {
  results: SearchResult[];
  took_ms: number;
}

export interface IngestChunk {
  content: string;
  chunk_index: number;
  sensitivity?: 'public' | 'restricted' | 'blocked';
  can_embed_externally?: boolean;
  metadata: Record<string, unknown>;
}

export interface IngestDocument {
  title: string;
  source_path: string;
  source_kind: string;
  checksum: string;
  chunks: IngestChunk[];
}

export interface AgentStats {
  agent: string;
  total_documents: number;
  total_chunks: number;
  embedded_chunks: number;
  blocked_chunks: number;
}

export class MemoryBusClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(opts: { baseUrl: string; apiKey: string }) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, '');
    this.apiKey = opts.apiKey;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        ...options.headers,
      },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`MemoryBus ${res.status}: ${body}`);
    }

    return res.json() as Promise<T>;
  }

  /** Semantic + lexical hybrid search */
  async search(
    agent: 'atlas' | 'zeus' | 'alexandria' | 'arquimedes',
    query: string,
    opts?: {
      topK?: number;
      sensitivityFilter?: string[];
      minScore?: number;
    },
  ): Promise<SearchResponse> {
    return this.request('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({
        agent,
        query,
        top_k: opts?.topK ?? 10,
        sensitivity_filter: opts?.sensitivityFilter ?? ['public', 'restricted'],
        hybrid: true,
        min_score: opts?.minScore ?? 0,
      }),
    });
  }

  /** Ingest documents with chunks */
  async ingest(
    agent: 'atlas' | 'zeus' | 'alexandria' | 'arquimedes',
    documents: IngestDocument[],
  ): Promise<{
    ingest_run_id: string;
    documents_count: number;
    chunks_count: number;
    embedded_count: number;
    blocked_count: number;
  }> {
    return this.request('/api/v1/ingest', {
      method: 'POST',
      body: JSON.stringify({ agent, documents }),
    });
  }

  /** Get per-agent statistics */
  async stats(
    agent: 'atlas' | 'zeus' | 'alexandria' | 'arquimedes',
  ): Promise<AgentStats> {
    return this.request(`/api/v1/agents/${agent}/stats`);
  }

  /** Health check */
  async health(): Promise<{ ok: boolean; service: string }> {
    return this.request('/health');
  }
}
