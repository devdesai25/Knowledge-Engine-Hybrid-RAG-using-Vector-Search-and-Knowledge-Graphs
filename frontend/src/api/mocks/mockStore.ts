import { DocumentItem, AdminUser, User, Role } from '@/types';
import { INITIAL_DOCUMENTS, INITIAL_ADMIN_USERS, SEEDED_USERS } from './seedData';
import { storage } from '@/lib/storage';

const MOCK_DOCS_KEY = 'ke_mock_documents';
const MOCK_USERS_KEY = 'ke_mock_admin_users';

function getStoredDocs(): DocumentItem[] {
  try {
    const raw = localStorage.getItem(MOCK_DOCS_KEY);
    return raw ? (JSON.parse(raw) as DocumentItem[]) : INITIAL_DOCUMENTS;
  } catch {
    return INITIAL_DOCUMENTS;
  }
}

function saveStoredDocs(docs: DocumentItem[]): void {
  try {
    localStorage.setItem(MOCK_DOCS_KEY, JSON.stringify(docs));
  } catch (e) {
    console.error('Failed to save mock docs to localStorage', e);
  }
}

function getStoredAdminUsers(): AdminUser[] {
  try {
    const raw = localStorage.getItem(MOCK_USERS_KEY);
    return raw ? (JSON.parse(raw) as AdminUser[]) : INITIAL_ADMIN_USERS;
  } catch {
    return INITIAL_ADMIN_USERS;
  }
}

function saveStoredAdminUsers(users: AdminUser[]): void {
  try {
    localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(users));
  } catch (e) {
    console.error('Failed to save mock admin users to localStorage', e);
  }
}

class MockStore {
  private documents: DocumentItem[] = getStoredDocs();
  private adminUsers: AdminUser[] = getStoredAdminUsers();
  private processingCounter: Record<string, number> = {};

  public resetToDefaults(): void {
    this.documents = [...INITIAL_DOCUMENTS];
    this.adminUsers = [...INITIAL_ADMIN_USERS];
    saveStoredDocs(this.documents);
    saveStoredAdminUsers(this.adminUsers);
    this.processingCounter = {};
  }

  public getCurrentUser(): User {
    const user = storage.getUser();
    if (user) return user;
    // Default to tenant A admin if nothing in storage
    const defaultUser = SEEDED_USERS['tenant-a-admin'];
    storage.setUser(defaultUser);
    storage.setToken('mock-token-tenant-a-admin');
    return defaultUser;
  }

  public getDocumentsForTenant(tenantId: string): DocumentItem[] {
    // Advance processing states on read for realism
    let updated = false;
    this.documents = this.documents.map((doc) => {
      if (doc.tenant_id === tenantId && doc.status === 'processing') {
        const count = (this.processingCounter[doc.id] || 0) + 1;
        this.processingCounter[doc.id] = count;
        // Turn ready after 2 polls
        if (count >= 2) {
          updated = true;
          return {
            ...doc,
            status: 'ready' as const,
            chunks: doc.chunks || Math.floor(Math.random() * 30) + 10,
          };
        }
      }
      return doc;
    });

    if (updated) {
      saveStoredDocs(this.documents);
    }

    return this.documents.filter((d) => d.tenant_id === tenantId);
  }

  public addDocuments(
    tenantId: string,
    uploadedBy: string,
    filenames: string[]
  ): { uploaded: number; failed: number; details: DocumentItem[] } {
    const newDocs: DocumentItem[] = [];

    filenames.forEach((filename) => {
      const id = `doc-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      // Simulate that files ending in .invalid fail, others succeed
      const isFailed = filename.toLowerCase().endsWith('.invalid');
      const doc: DocumentItem = {
        id,
        filename,
        status: isFailed ? 'failed' : 'processing',
        uploaded_by: uploadedBy,
        created_at: new Date().toISOString(),
        chunks: isFailed ? 0 : Math.floor(Math.random() * 40) + 5,
        tenant_id: tenantId,
        error: isFailed ? 'Unsupported file format or corrupted content' : undefined,
      };
      newDocs.push(doc);
    });

    this.documents = [...newDocs, ...this.documents];
    saveStoredDocs(this.documents);

    return {
      uploaded: newDocs.filter((d) => d.status !== 'failed').length,
      failed: newDocs.filter((d) => d.status === 'failed').length,
      details: newDocs,
    };
  }

  public deleteDocument(tenantId: string, docId: string): boolean {
    const index = this.documents.findIndex((d) => d.id === docId && d.tenant_id === tenantId);
    if (index === -1) return false;
    this.documents.splice(index, 1);
    saveStoredDocs(this.documents);
    return true;
  }

  public getAdminUsersForTenant(tenantId: string): AdminUser[] {
    return this.adminUsers.filter((u) => u.tenant_id === tenantId);
  }

  public inviteUser(tenantId: string, email: string, role: Role): AdminUser {
    const existing = this.adminUsers.find(
      (u) => u.tenant_id === tenantId && u.email.toLowerCase() === email.toLowerCase()
    );
    if (existing) {
      throw new Error(`User with email "${email}" already exists in this tenant.`);
    }

    const newUser: AdminUser = {
      id: `user-${Date.now()}`,
      email,
      role,
      created_at: new Date().toISOString(),
      tenant_id: tenantId,
    };

    this.adminUsers = [newUser, ...this.adminUsers];
    saveStoredAdminUsers(this.adminUsers);
    return newUser;
  }
}

export const mockStore = new MockStore();
