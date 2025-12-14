/**
 * AI AutoForm - API Client
 * バックエンドAPIとの通信を管理
 */

class APIClient {
    constructor(baseURL = null) {
        // GitHub Codespaces対応: 現在のホストからAPIのURLを推測
        if (!baseURL) {
            const currentHost = window.location.host;
            if (currentHost.includes('app.github.dev')) {
                // Codespacesの場合: ポート番号を5000に変更
                this.baseURL = window.location.protocol + '//' + currentHost.replace('-8000.', '-5000.');
            } else {
                // ローカル開発の場合
                this.baseURL = 'http://localhost:5000';
            }
        } else {
            this.baseURL = baseURL;
        }
        console.log('API Base URL:', this.baseURL);
    }

    /**
     * HTTP リクエストを送信
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP Error: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // ========================================
    // Health Check
    // ========================================
    async healthCheck() {
        return await this.request('/api/health');
    }

    // ========================================
    // Companies API
    // ========================================
    async getCompanies() {
        return await this.request('/api/companies');
    }

    async createCompany(data) {
        return await this.request('/api/companies', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async analyzeCompany(companyId) {
        return await this.request(`/api/companies/${companyId}/analyze`, {
            method: 'POST'
        });
    }

    // ========================================
    // Projects API
    // ========================================
    async getProjects() {
        return await this.request('/api/projects');
    }

    async createProject(data) {
        return await this.request('/api/projects', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // ========================================
    // Workers API
    // ========================================
    async getWorkers() {
        return await this.request('/api/workers');
    }

    async createWorker(data) {
        return await this.request('/api/workers', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
}

// グローバルインスタンス
const apiClient = new APIClient();
