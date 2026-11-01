import { User, DocumentItem, AdminUser, Citation } from '@/types';

export const SEEDED_USERS: Record<string, User> = {
  'tenant-a-admin': {
    id: 'user-tenant-a-admin',
    email: 'admin@acme.com',
    role: 'admin',
    tenant: {
      id: 'tenant-acme',
      name: 'Acme Corp',
    },
  },
  'tenant-a-member': {
    id: 'user-tenant-a-member',
    email: 'member@acme.com',
    role: 'member',
    tenant: {
      id: 'tenant-acme',
      name: 'Acme Corp',
    },
  },
  'tenant-b-member': {
    id: 'user-tenant-b-member',
    email: 'member@globex.com',
    role: 'member',
    tenant: {
      id: 'tenant-globex',
      name: 'Globex Corporation',
    },
  },
};

export const INITIAL_DOCUMENTS: DocumentItem[] = [
  // Tenant Acme
  {
    id: 'doc-acme-1',
    filename: 'acme_product_specifications_v3.pdf',
    status: 'ready',
    uploaded_by: 'admin@acme.com',
    created_at: '2026-10-15T09:30:00Z',
    chunks: 42,
    tenant_id: 'tenant-acme',
  },
  {
    id: 'doc-acme-2',
    filename: 'q3_financial_performance.xlsx',
    status: 'ready',
    uploaded_by: 'admin@acme.com',
    created_at: '2026-10-20T14:15:00Z',
    chunks: 18,
    tenant_id: 'tenant-acme',
  },
  {
    id: 'doc-acme-3',
    filename: 'cloud_security_whitepaper.docx',
    status: 'ready',
    uploaded_by: 'admin@acme.com',
    created_at: '2026-10-24T11:00:00Z',
    chunks: 64,
    tenant_id: 'tenant-acme',
  },
  {
    id: 'doc-acme-4',
    filename: 'enterprise_sla_guidelines.md',
    status: 'ready',
    uploaded_by: 'admin@acme.com',
    created_at: '2026-10-28T16:45:00Z',
    chunks: 12,
    tenant_id: 'tenant-acme',
  },
  {
    id: 'doc-acme-5',
    filename: 'raw_customer_telemetry_oct.csv',
    status: 'processing',
    uploaded_by: 'admin@acme.com',
    created_at: '2026-10-31T08:10:00Z',
    chunks: 0,
    tenant_id: 'tenant-acme',
  },

  // Tenant Globex
  {
    id: 'doc-globex-1',
    filename: 'globex_global_supply_chain_strategy.pdf',
    status: 'ready',
    uploaded_by: 'admin@globex.com',
    created_at: '2026-09-12T10:00:00Z',
    chunks: 85,
    tenant_id: 'tenant-globex',
  },
  {
    id: 'doc-globex-2',
    filename: 'warehouse_automation_report.pptx',
    status: 'ready',
    uploaded_by: 'admin@globex.com',
    created_at: '2026-10-02T13:20:00Z',
    chunks: 31,
    tenant_id: 'tenant-globex',
  },
  {
    id: 'doc-globex-3',
    filename: 'employee_conduct_policy_2026.pdf',
    status: 'ready',
    uploaded_by: 'admin@globex.com',
    created_at: '2026-10-18T09:45:00Z',
    chunks: 25,
    tenant_id: 'tenant-globex',
  },
  {
    id: 'doc-globex-4',
    filename: 'eu_customs_compliance_checklist.json',
    status: 'ready',
    uploaded_by: 'admin@globex.com',
    created_at: '2026-10-29T15:30:00Z',
    chunks: 14,
    tenant_id: 'tenant-globex',
  },
];

export const INITIAL_ADMIN_USERS: AdminUser[] = [
  // Tenant Acme
  {
    id: 'user-tenant-a-admin',
    email: 'admin@acme.com',
    role: 'admin',
    created_at: '2026-01-10T08:00:00Z',
    tenant_id: 'tenant-acme',
  },
  {
    id: 'user-tenant-a-member',
    email: 'member@acme.com',
    role: 'member',
    created_at: '2026-02-14T10:30:00Z',
    tenant_id: 'tenant-acme',
  },
  {
    id: 'user-acme-3',
    email: 'sarah.chen@acme.com',
    role: 'member',
    created_at: '2026-04-01T11:15:00Z',
    tenant_id: 'tenant-acme',
  },
  {
    id: 'user-acme-4',
    email: 'devon.ross@acme.com',
    role: 'member',
    created_at: '2026-06-18T14:40:00Z',
    tenant_id: 'tenant-acme',
  },

  // Tenant Globex
  {
    id: 'user-globex-admin',
    email: 'admin@globex.com',
    role: 'admin',
    created_at: '2026-01-05T09:00:00Z',
    tenant_id: 'tenant-globex',
  },
  {
    id: 'user-tenant-b-member',
    email: 'member@globex.com',
    role: 'member',
    created_at: '2026-03-22T13:00:00Z',
    tenant_id: 'tenant-globex',
  },
  {
    id: 'user-globex-3',
    email: 'logistics.lead@globex.com',
    role: 'member',
    created_at: '2026-05-19T16:20:00Z',
    tenant_id: 'tenant-globex',
  },
];

export const MOCK_TENANT_CHAT_RESPONSES: Record<
  string,
  {
    answerTemplate: (query: string) => string;
    citations: Citation[];
  }
> = {
  'tenant-acme': {
    answerTemplate: (query: string) =>
      `### Acme Corp Knowledge Engine Response\n\nBased on **Acme Corp's internal documentation** for query: "${query}":\n\n1. **Service Level Agreement (SLA):** Acme guarantees **99.99% uptime** across all regional compute clusters, with automated failover executing in under 350ms.\n2. **Security & Encryption:** All documents and vector embeddings are encrypted at rest using AES-256-GCM, and TLS 1.3 is enforced end-to-end.\n3. **Financial Outlook:** As outlined in the Q3 summary, operating efficiency increased by 18.4% YoY following the hybrid vector search rollout.\n\nPlease refer to the verified citation fragments below for exact section references.`,
    citations: [
      {
        document_id: 'doc-acme-4',
        filename: 'enterprise_sla_guidelines.md',
        page_no: 3,
        headings: ['System Availability', 'Tier-1 High Availability Targets'],
        text: 'Acme infrastructure commits to a minimum of 99.99% monthly availability for Enterprise tier tenants. Automated failover between availability zones is configured with sub-350ms latency guarantees.',
        score: 0.94,
      },
      {
        document_id: 'doc-acme-3',
        filename: 'cloud_security_whitepaper.docx',
        page_no: 12,
        headings: ['Cryptographic Standards', 'At-Rest & In-Transit Protocols'],
        text: 'All tenant knowledge stores and vector indexes are compartmentalized. Data encryption at rest applies AES-256 with tenant-isolated key management, preventing cross-tenant vector leakage.',
        score: 0.88,
      },
      {
        document_id: 'doc-acme-1',
        filename: 'acme_product_specifications_v3.pdf',
        page_no: 7,
        headings: ['Architecture', 'Hybrid Search Orchestration'],
        text: 'The hybrid search pipeline combines dense semantic embeddings with sparse lexical bm25 indexers, re-ranking candidate passages via cross-encoders before prompt compilation.',
        score: 0.82,
      },
    ],
  },

  'tenant-globex': {
    answerTemplate: (query: string) =>
      `### Globex Corporation Operations Report\n\nAccording to **Globex Corporation's supply chain and logistics index** for query: "${query}":\n\n1. **Global Distribution Logistics:** Globex operates 14 regional fulfillment hubs across EMEA, APAC, and the Americas, achieving an average cross-border shipping turnaround of 48 hours.\n2. **Warehouse Automation:** Automated Guided Vehicles (AGVs) handle 82% of pallet transport across primary distribution facilities.\n3. **Compliance:** All cross-border shipments adhere strictly to EU customs compliance and automated export declaration frameworks.\n\nSee below for the specific source excerpts retrieved from Globex documents.`,
    citations: [
      {
        document_id: 'doc-globex-1',
        filename: 'globex_global_supply_chain_strategy.pdf',
        page_no: 18,
        headings: ['Fulfillment Hubs', 'Cross-Border Lead Times'],
        text: 'Globex Corporation maintains 14 strategic multi-modal distribution centers. Through synchronized routing algorithms, average cross-border shipping turnaround has been reduced to under 48 hours.',
        score: 0.93,
      },
      {
        document_id: 'doc-globex-2',
        filename: 'warehouse_automation_report.pptx',
        page_no: 5,
        headings: ['Robotics & Automation', 'AGV Fleet Deployment'],
        text: 'Deployment of 120 Autonomous Mobile Robots (AMRs) and AGVs has accelerated container unloading cycles by 41%, maintaining zero safety incidents in Q3.',
        score: 0.87,
      },
      {
        document_id: 'doc-globex-4',
        filename: 'eu_customs_compliance_checklist.json',
        page_no: 1,
        headings: ['Import/Export Controls', 'Automated Declarations'],
        text: 'Automated electronic declaration pipelines validate HS codes and tariff compliance in real-time, avoiding port customs demurrage penalties.',
        score: 0.79,
      },
    ],
  },
};
