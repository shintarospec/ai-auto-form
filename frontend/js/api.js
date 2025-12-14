/**
 * API Client for AI AutoForm
 * フロントエンドからバックエンドAPIを呼び出すためのクライアントモジュール
 */

// GitHub Codespaces対応: 現在のホストからAPIのURLを推測
let API_BASE_URL;
if (typeof window !== 'undefined') {
    const currentHost = window.location.host;
    if (currentHost.includes('app.github.dev')) {
        // Codespacesの場合: ポート番号を8000から5001に変更
        API_BASE_URL = window.location.protocol + '//' + currentHost.replace('-8000.', '-5001.') + '/api';
    } else {
        // ローカル開発の場合
        API_BASE_URL = 'http://localhost:5001/api';
    }
    console.log('🔗 API Base URL:', API_BASE_URL);
}

/**
 * 共通のfetchラッパー
 * @param {string} endpoint - APIエンドポイント
 * @param {object} options - fetchオプション
 * @returns {Promise<object>} レスポンスデータ
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
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
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

/**
 * Workers API
 */
const WorkersAPI = {
    /**
     * 全作業者を取得
     * @returns {Promise<Array>} 作業者リスト
     */
    async getAll() {
        return apiRequest('/workers');
    },

    /**
     * 特定の作業者を取得
     * @param {number} id - 作業者ID
     * @returns {Promise<object>} 作業者データ
     */
    async getById(id) {
        return apiRequest(`/workers/${id}`);
    },

    /**
     * 作業者を作成
     * @param {object} workerData - 作業者データ {name, email, skill_level}
     * @returns {Promise<object>} 作成された作業者データ
     */
    async create(workerData) {
        return apiRequest('/workers', {
            method: 'POST',
            body: JSON.stringify(workerData)
        });
    },

    /**
     * 作業者を更新
     * @param {number} id - 作業者ID
     * @param {object} workerData - 更新データ
     * @returns {Promise<object>} 更新された作業者データ
     */
    async update(id, workerData) {
        return apiRequest(`/workers/${id}`, {
            method: 'PUT',
            body: JSON.stringify(workerData)
        });
    },

    /**
     * 作業者を削除
     * @param {number} id - 作業者ID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/workers/${id}`, {
            method: 'DELETE'
        });
    },

    /**
     * 作業者にポイントを追加
     * @param {number} id - 作業者ID
     * @param {number} points - 追加ポイント数
     * @returns {Promise<object>} 更新された作業者データ
     */
    async addPoints(id, points) {
        return apiRequest(`/workers/${id}/add-points`, {
            method: 'POST',
            body: JSON.stringify({ points })
        });
    }
};

/**
 * Products API
 */
const ProductsAPI = {
    /**
     * 全商品を取得
     * @returns {Promise<Array>} 商品リスト
     */
    async getAll() {
        return apiRequest('/products');
    },

    /**
     * 特定の商品を取得
     * @param {number} id - 商品ID
     * @returns {Promise<object>} 商品データ
     */
    async getById(id) {
        return apiRequest(`/products/${id}`);
    },

    /**
     * 商品を作成
     * @param {object} productData - 商品データ {name, price, description}
     * @returns {Promise<object>} 作成された商品データ
     */
    async create(productData) {
        return apiRequest('/products', {
            method: 'POST',
            body: JSON.stringify(productData)
        });
    },

    /**
     * 商品を更新
     * @param {number} id - 商品ID
     * @param {object} productData - 更新データ
     * @returns {Promise<object>} 更新された商品データ
     */
    async update(id, productData) {
        return apiRequest(`/products/${id}`, {
            method: 'PUT',
            body: JSON.stringify(productData)
        });
    },

    /**
     * 商品を削除
     * @param {number} id - 商品ID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/products/${id}`, {
            method: 'DELETE'
        });
    }
};

/**
 * Target Lists API
 */
const TargetListsAPI = {
    /**
     * 全ターゲットリストを取得
     * @returns {Promise<Array>} ターゲットリスト
     */
    async getAll() {
        return apiRequest('/targets/lists');
    },

    /**
     * 特定のターゲットリストを取得
     * @param {number} id - リストID
     * @returns {Promise<object>} リストデータ
     */
    async getById(id) {
        return apiRequest(`/targets/lists/${id}`);
    },

    /**
     * ターゲットリストを作成
     * @param {object} listData - リストデータ {name}
     * @returns {Promise<object>} 作成されたリストデータ
     */
    async create(listData) {
        return apiRequest('/targets/lists', {
            method: 'POST',
            body: JSON.stringify(listData)
        });
    },

    /**
     * ターゲットリストを更新
     * @param {number} id - リストID
     * @param {object} listData - 更新データ
     * @returns {Promise<object>} 更新されたリストデータ
     */
    async update(id, listData) {
        return apiRequest(`/targets/lists/${id}`, {
            method: 'PUT',
            body: JSON.stringify(listData)
        });
    },

    /**
     * ターゲットリストを削除
     * @param {number} id - リストID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/targets/lists/${id}`, {
            method: 'DELETE'
        });
    }
};

/**
 * Target Companies API
 */
const TargetCompaniesAPI = {
    /**
     * 特定リストの企業を取得
     * @param {number} listId - リストID
     * @returns {Promise<Array>} 企業リスト
     */
    async getByListId(listId) {
        return apiRequest(`/targets/companies?target_list_id=${listId}`);
    },

    /**
     * 企業を追加
     * @param {object} companyData - 企業データ {target_list_id, company_name, company_url, industry}
     * @returns {Promise<object>} 作成された企業データ
     */
    async create(companyData) {
        return apiRequest('/targets/companies', {
            method: 'POST',
            body: JSON.stringify(companyData)
        });
    },

    /**
     * 企業を一括追加（CSV）
     * @param {number} listId - リストID
     * @param {Array} companies - 企業配列 [{company_name, company_url, industry}]
     * @returns {Promise<object>} 追加結果
     */
    async bulkCreate(listId, companies) {
        return apiRequest('/targets/companies/bulk', {
            method: 'POST',
            body: JSON.stringify({
                target_list_id: listId,
                companies: companies
            })
        });
    },

    /**
     * 企業を更新
     * @param {number} id - 企業ID
     * @param {object} companyData - 更新データ
     * @returns {Promise<object>} 更新された企業データ
     */
    async update(id, companyData) {
        return apiRequest(`/targets/companies/${id}`, {
            method: 'PUT',
            body: JSON.stringify(companyData)
        });
    },

    /**
     * 企業を削除
     * @param {number} id - 企業ID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/targets/companies/${id}`, {
            method: 'DELETE'
        });
    }
};

/**
 * Projects API
 */
const ProjectsAPI = {
    /**
     * 全プロジェクトを取得
     * @returns {Promise<Array>} プロジェクトリスト
     */
    async getAll() {
        return apiRequest('/projects');
    },

    /**
     * 特定のプロジェクトを取得
     * @param {number} id - プロジェクトID
     * @returns {Promise<object>} プロジェクトデータ
     */
    async getById(id) {
        return apiRequest(`/projects/${id}`);
    },

    /**
     * プロジェクトを作成（タスクも自動生成）
     * @param {object} projectData - プロジェクトデータ {name, target_list_id, product_id, worker_ids}
     * @returns {Promise<object>} 作成されたプロジェクトデータ
     */
    async create(projectData) {
        return apiRequest('/projects', {
            method: 'POST',
            body: JSON.stringify(projectData)
        });
    },

    /**
     * プロジェクトを更新
     * @param {number} id - プロジェクトID
     * @param {object} projectData - 更新データ
     * @returns {Promise<object>} 更新されたプロジェクトデータ
     */
    async update(id, projectData) {
        return apiRequest(`/projects/${id}`, {
            method: 'PUT',
            body: JSON.stringify(projectData)
        });
    },

    /**
     * プロジェクトを削除
     * @param {number} id - プロジェクトID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/projects/${id}`, {
            method: 'DELETE'
        });
    },

    /**
     * プロジェクト統計を取得
     * @param {number} id - プロジェクトID
     * @returns {Promise<object>} 統計データ
     */
    async getStats(id) {
        return apiRequest(`/projects/${id}/stats`);
    }
};

/**
 * Tasks API
 */
const TasksAPI = {
    /**
     * タスクを取得（フィルタ可能）
     * @param {object} params - クエリパラメータ {project_id?, worker_id?, status?}
     * @returns {Promise<Array>} タスクリスト
     */
    async getAll(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/tasks?${queryString}` : '/tasks';
        return apiRequest(endpoint);
    },

    /**
     * 特定のタスクを取得
     * @param {number} id - タスクID
     * @returns {Promise<object>} タスクデータ
     */
    async getById(id) {
        return apiRequest(`/tasks/${id}`);
    },

    /**
     * タスクを作成
     * @param {object} taskData - タスクデータ {project_id, worker_id, company_name, company_url}
     * @returns {Promise<object>} 作成されたタスクデータ
     */
    async create(taskData) {
        return apiRequest('/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    },

    /**
     * タスクを更新
     * @param {number} id - タスクID
     * @param {object} taskData - 更新データ
     * @returns {Promise<object>} 更新されたタスクデータ
     */
    async update(id, taskData) {
        return apiRequest(`/tasks/${id}`, {
            method: 'PUT',
            body: JSON.stringify(taskData)
        });
    },

    /**
     * タスクを削除
     * @param {number} id - タスクID
     * @returns {Promise<object>} 削除結果
     */
    async delete(id) {
        return apiRequest(`/tasks/${id}`, {
            method: 'DELETE'
        });
    },

    /**
     * タスクを提出（フォーム自動化実行）
     * @param {number} id - タスクID
     * @param {object} data - 提出データ {message, screenshot_path?}
     * @returns {Promise<object>} 提出結果
     */
    async submit(id, data) {
        return apiRequest(`/tasks/${id}/submit`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * タスクをNG判定
     * @param {number} id - タスクID
     * @returns {Promise<object>} 更新結果
     */
    async markAsNG(id) {
        return apiRequest(`/tasks/${id}/ng`, {
            method: 'POST'
        });
    },

    /**
     * タスクをスキップ
     * @param {number} id - タスクID
     * @returns {Promise<object>} 更新結果
     */
    async skip(id) {
        return apiRequest(`/tasks/${id}/skip`, {
            method: 'POST'
        });
    },

    /**
     * タスクをリセット
     * @param {number} id - タスクID
     * @returns {Promise<object>} 更新結果
     */
    async reset(id) {
        return apiRequest(`/tasks/${id}/reset`, {
            method: 'POST'
        });
    }
};

/**
 * エクスポート
 */
window.API = {
    Workers: WorkersAPI,
    Products: ProductsAPI,
    TargetLists: TargetListsAPI,
    TargetCompanies: TargetCompaniesAPI,
    Projects: ProjectsAPI,
    Tasks: TasksAPI
};
