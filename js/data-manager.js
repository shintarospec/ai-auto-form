/**
 * AI AutoForm - Data Manager
 * LocalStorageベースのデータ管理システム
 */

class DataManager {
    constructor() {
        this.initializeData();
    }

    // ========================================
    // 初期化
    // ========================================
    initializeData() {
        if (!localStorage.getItem('aiautoform_initialized')) {
            this.resetToDefaultData();
            localStorage.setItem('aiautoform_initialized', 'true');
        }
    }

    resetToDefaultData() {
        // 企業リスト
        const companies = [
            {
                id: 1,
                name: 'テックイノベーション株式会社',
                url: 'https://techinnovation.example.com',
                industry: '製造業DXコンサルティング',
                analyzed: true,
                analysisData: {
                    businessDescription: '製造業向けのデジタルトランスフォーメーション支援。現場目線での課題解決が強み。',
                    strengths: ['現場経験豊富なコンサルタント', '中小企業向けの実践的アプローチ', '導入後のサポート体制'],
                    targetCustomers: '中堅・中小の製造業',
                    keyTopics: ['生産性向上', '品質管理', '業務効率化']
                },
                formUrl: 'https://techinnovation.example.com/contact',
                createdAt: '2025-12-10',
                listId: 1
            },
            {
                id: 2,
                name: 'グローバルトレード株式会社',
                url: 'https://globaltrade.example.com',
                industry: '貿易・輸出入',
                analyzed: true,
                analysisData: {
                    businessDescription: 'アジア圏を中心とした貿易業務。特に東南アジア市場に強み。',
                    strengths: ['独自の物流ネットワーク', '多言語対応', '関税・規制対応'],
                    targetCustomers: '海外展開を目指す中小企業',
                    keyTopics: ['越境EC', '輸出支援', 'サプライチェーン']
                },
                formUrl: 'https://globaltrade.example.com/inquiry',
                createdAt: '2025-12-10',
                listId: 1
            },
            {
                id: 3,
                name: '株式会社デジタルマーケティングラボ',
                url: 'https://dmlab.example.com',
                industry: 'デジタルマーケティング',
                analyzed: false,
                analysisData: null,
                formUrl: 'https://dmlab.example.com/contact',
                createdAt: '2025-12-11',
                listId: 1
            },
            {
                id: 4,
                name: '株式会社クラウドソリューションズ',
                url: 'https://cloudsol.example.com',
                industry: 'SaaS開発',
                analyzed: false,
                analysisData: null,
                formUrl: null,
                createdAt: '2025-12-12',
                listId: 2
            },
            {
                id: 5,
                name: '株式会社エコエナジー',
                url: 'https://ecoenergy.example.com',
                industry: '再生可能エネルギー',
                analyzed: true,
                analysisData: {
                    businessDescription: '太陽光発電システムの設計・施工。企業向け大規模案件が得意。',
                    strengths: ['施工実績1000件以上', '自社開発の監視システム', '20年保証'],
                    targetCustomers: '工場・物流施設など',
                    keyTopics: ['脱炭素', 'コスト削減', '補助金活用']
                },
                formUrl: 'https://ecoenergy.example.com/business-inquiry',
                createdAt: '2025-12-12',
                listId: 2
            }
        ];

        // 案件・商材
        const projects_db = [
            {
                id: 1,
                name: 'AI業務自動化ツール',
                description: 'コンサルティング業務における定型作業を自動化するAIツール',
                targetIndustry: 'コンサルティング、士業',
                strengths: ['導入が簡単', '月額2万円から', '専任サポート付き'],
                promptTemplate: `{company_name}様

突然のご連絡失礼いたします。
株式会社AIソリューションズの{sender_name}と申します。

貴社のWebサイトを拝見し、特に「{key_topic}」における取り組みに大変感銘を受けました。

弊社は、{target_industry}における「定型業務の自動化」を支援するAIツールを提供しております。
貴社の{business_description}において、よりコアな業務に集中できる環境作りにお役に立てるのではないかと考え、ご連絡いたしました。

詳細な資料をお送り可能です。もしご興味をお持ちいただけましたら、ご返信いただけますと幸いです。`,
                createdAt: '2025-12-01',
                status: 'active'
            },
            {
                id: 2,
                name: 'クラウド経費精算システム',
                description: '中小企業向けのシンプルで使いやすい経費精算SaaS',
                targetIndustry: '全業種',
                strengths: ['初期費用0円', 'スマホアプリ対応', '会計ソフト連携'],
                promptTemplate: `{company_name}
ご担当者様

{sender_company}の{sender_name}と申します。

貴社のような{industry}企業様において、経費精算業務の効率化ニーズが高まっていると伺い、ご連絡いたしました。

弊社の「クラウド経費精算システム」は、{strengths}といった特徴があり、導入企業様から「申請から承認まで80%時間短縮できた」とのお声をいただいております。

無料トライアルもご用意しておりますので、ぜひ一度お試しいただけますと幸いです。`,
                createdAt: '2025-12-05',
                status: 'active'
            }
        ];

        // 作業者
        const workers = [
            {
                id: 1,
                name: '山田 太郎',
                email: 'yamada@example.com',
                status: 'active',
                rank: 'Gold',
                totalPoints: 45800,
                monthlyPoints: 12400,
                joinedAt: '2025-10-01',
                avatar: 'YM',
                completedTasks: 916
            },
            {
                id: 2,
                name: '佐藤 花子',
                email: 'sato@example.com',
                status: 'active',
                rank: 'Platinum',
                totalPoints: 68200,
                monthlyPoints: 15600,
                joinedAt: '2025-09-15',
                avatar: 'SH',
                completedTasks: 1364
            },
            {
                id: 3,
                name: '田中 一郎',
                email: 'tanaka@example.com',
                status: 'active',
                rank: 'Silver',
                totalPoints: 22100,
                monthlyPoints: 8300,
                joinedAt: '2025-11-10',
                avatar: 'TI',
                completedTasks: 442
            },
            {
                id: 4,
                name: '鈴木 美咲',
                email: 'suzuki@example.com',
                status: 'inactive',
                rank: 'Bronze',
                totalPoints: 5600,
                monthlyPoints: 0,
                joinedAt: '2025-11-20',
                avatar: 'SM',
                completedTasks: 112
            }
        ];

        // プロジェクト
        const projects = [
            {
                id: 1,
                name: '製造業DX企業向けAIツール営業',
                companyListId: 1,
                productId: 1,
                assignedWorkers: [1, 2],
                status: 'active',
                totalTargets: 100,
                completed: 46,
                rewardPerTask: 50,
                deadline: '2025-12-31',
                createdAt: '2025-12-08',
                aiAnalysisCompleted: true
            },
            {
                id: 2,
                name: '全業種向け経費精算システム',
                companyListId: 2,
                productId: 2,
                assignedWorkers: [1, 3],
                status: 'active',
                totalTargets: 150,
                completed: 23,
                rewardPerTask: 40,
                deadline: '2026-01-15',
                createdAt: '2025-12-10',
                aiAnalysisCompleted: true
            },
            {
                id: 3,
                name: '貿易企業向けAIツール（準備中）',
                companyListId: 1,
                productId: 1,
                assignedWorkers: [2],
                status: 'analyzing',
                totalTargets: 300,
                completed: 0,
                rewardPerTask: 50,
                deadline: '2026-01-31',
                createdAt: '2025-12-12',
                aiAnalysisCompleted: false
            },
            {
                id: 4,
                name: '再エネ企業向け営業（完了）',
                companyListId: 2,
                productId: 2,
                assignedWorkers: [2, 3],
                status: 'completed',
                totalTargets: 50,
                completed: 50,
                rewardPerTask: 60,
                deadline: '2025-12-10',
                createdAt: '2025-11-20',
                aiAnalysisCompleted: true
            }
        ];

        // タスク（作業者が実行する個別の送信タスク）
        const tasks = [];
        let taskId = 1;
        
        // プロジェクト1のタスク生成
        for (let i = 1; i <= 100; i++) {
            const companyId = i <= 5 ? i : (i % 5) + 1;
            tasks.push({
                id: taskId++,
                projectId: 1,
                companyId: companyId,
                assignedWorkerId: i % 2 === 0 ? 1 : 2,
                status: i <= 46 ? 'completed' : 'pending',
                generatedMessage: this.generateMockMessage(companyId, 1),
                completedAt: i <= 46 ? '2025-12-13' : null,
                rewardPoints: i <= 46 ? 50 : 0
            });
        }

        // プロジェクト2のタスク生成
        for (let i = 1; i <= 150; i++) {
            const companyId = (i % 5) + 1;
            tasks.push({
                id: taskId++,
                projectId: 2,
                companyId: companyId,
                assignedWorkerId: i % 2 === 0 ? 1 : 3,
                status: i <= 23 ? 'completed' : 'pending',
                generatedMessage: this.generateMockMessage(companyId, 2),
                completedAt: i <= 23 ? '2025-12-13' : null,
                rewardPoints: i <= 23 ? 40 : 0
            });
        }

        // データ保存
        this.saveData('companies', companies);
        this.saveData('products', projects_db);
        this.saveData('workers', workers);
        this.saveData('projects', projects);
        this.saveData('tasks', tasks);

        // 統計データ
        this.saveData('stats', {
            totalSentToday: 45,
            totalSentMonth: 1203,
            activeProjects: 2,
            activeWorkers: 3,
            pendingAIAnalysis: 12
        });
    }

    generateMockMessage(companyId, productId) {
        const company = this.getCompanyById(companyId);
        const product = this.getProductById(productId);
        
        if (!company || !product) return '';

        const template = product.promptTemplate;
        const analysisData = company.analysisData || {};

        return template
            .replace('{company_name}', company.name)
            .replace('{sender_name}', '山田')
            .replace('{sender_company}', '株式会社AIソリューションズ')
            .replace('{key_topic}', analysisData.keyTopics ? analysisData.keyTopics[0] : '事業内容')
            .replace('{target_industry}', product.targetIndustry)
            .replace('{business_description}', analysisData.businessDescription || '貴社の事業')
            .replace('{industry}', company.industry)
            .replace('{strengths}', product.strengths.join('、'));
    }

    // ========================================
    // データ取得
    // ========================================
    getData(key) {
        const data = localStorage.getItem(`aiautoform_${key}`);
        return data ? JSON.parse(data) : null;
    }

    saveData(key, value) {
        localStorage.setItem(`aiautoform_${key}`, JSON.stringify(value));
    }

    // 企業リスト
    getCompanies() {
        return this.getData('companies') || [];
    }

    getCompanyById(id) {
        const companies = this.getCompanies();
        return companies.find(c => c.id === id);
    }

    addCompany(company) {
        const companies = this.getCompanies();
        company.id = this.getNextId(companies);
        company.createdAt = new Date().toISOString().split('T')[0];
        company.analyzed = false;
        company.analysisData = null;
        companies.push(company);
        this.saveData('companies', companies);
        return company;
    }

    updateCompany(id, updates) {
        const companies = this.getCompanies();
        const index = companies.findIndex(c => c.id === id);
        if (index !== -1) {
            companies[index] = { ...companies[index], ...updates };
            this.saveData('companies', companies);
            return companies[index];
        }
        return null;
    }

    deleteCompany(id) {
        const companies = this.getCompanies();
        const filtered = companies.filter(c => c.id !== id);
        this.saveData('companies', filtered);
    }

    // 案件・商材
    getProducts() {
        return this.getData('products') || [];
    }

    getProductById(id) {
        const products = this.getProducts();
        return products.find(p => p.id === id);
    }

    addProduct(product) {
        const products = this.getProducts();
        product.id = this.getNextId(products);
        product.createdAt = new Date().toISOString().split('T')[0];
        product.status = 'active';
        products.push(product);
        this.saveData('products', products);
        return product;
    }

    updateProduct(id, updates) {
        const products = this.getProducts();
        const index = products.findIndex(p => p.id === id);
        if (index !== -1) {
            products[index] = { ...products[index], ...updates };
            this.saveData('products', products);
            return products[index];
        }
        return null;
    }

    deleteProduct(id) {
        const products = this.getProducts();
        const filtered = products.filter(p => p.id !== id);
        this.saveData('products', filtered);
    }

    // 作業者
    getWorkers() {
        return this.getData('workers') || [];
    }

    getWorkerById(id) {
        const workers = this.getWorkers();
        return workers.find(w => w.id === id);
    }

    addWorker(worker) {
        const workers = this.getWorkers();
        worker.id = this.getNextId(workers);
        worker.joinedAt = new Date().toISOString().split('T')[0];
        worker.status = 'active';
        worker.totalPoints = 0;
        worker.monthlyPoints = 0;
        worker.completedTasks = 0;
        worker.rank = 'Bronze';
        workers.push(worker);
        this.saveData('workers', workers);
        return worker;
    }

    updateWorker(id, updates) {
        const workers = this.getWorkers();
        const index = workers.findIndex(w => w.id === id);
        if (index !== -1) {
            workers[index] = { ...workers[index], ...updates };
            this.saveData('workers', workers);
            return workers[index];
        }
        return null;
    }

    deleteWorker(id) {
        const workers = this.getWorkers();
        const filtered = workers.filter(w => w.id !== id);
        this.saveData('workers', filtered);
    }

    // プロジェクト
    getProjects() {
        return this.getData('projects') || [];
    }

    getProjectById(id) {
        const projects = this.getProjects();
        return projects.find(p => p.id === id);
    }

    addProject(project) {
        const projects = this.getProjects();
        project.id = this.getNextId(projects);
        project.createdAt = new Date().toISOString().split('T')[0];
        project.status = 'analyzing';
        project.completed = 0;
        project.aiAnalysisCompleted = false;
        projects.push(project);
        this.saveData('projects', projects);
        return project;
    }

    updateProject(id, updates) {
        const projects = this.getProjects();
        const index = projects.findIndex(p => p.id === id);
        if (index !== -1) {
            projects[index] = { ...projects[index], ...updates };
            this.saveData('projects', projects);
            return projects[index];
        }
        return null;
    }

    deleteProject(id) {
        const projects = this.getProjects();
        const filtered = projects.filter(p => p.id !== id);
        this.saveData('projects', filtered);
    }

    // タスク
    getTasks() {
        return this.getData('tasks') || [];
    }

    getTasksByProject(projectId) {
        const tasks = this.getTasks();
        return tasks.filter(t => t.projectId === projectId);
    }

    getTasksByWorker(workerId) {
        const tasks = this.getTasks();
        return tasks.filter(t => t.assignedWorkerId === workerId);
    }

    getPendingTasksForWorker(workerId) {
        const tasks = this.getTasks();
        return tasks.filter(t => t.assignedWorkerId === workerId && t.status === 'pending');
    }

    updateTask(id, updates) {
        const tasks = this.getTasks();
        const index = tasks.findIndex(t => t.id === id);
        if (index !== -1) {
            tasks[index] = { ...tasks[index], ...updates };
            this.saveData('tasks', tasks);
            return tasks[index];
        }
        return null;
    }

    completeTask(taskId, workerId) {
        const task = this.updateTask(taskId, {
            status: 'completed',
            completedAt: new Date().toISOString().split('T')[0]
        });

        if (task) {
            // プロジェクトの完了数を更新
            const project = this.getProjectById(task.projectId);
            if (project) {
                this.updateProject(project.id, {
                    completed: project.completed + 1
                });
            }

            // ワーカーのポイントを更新
            const worker = this.getWorkerById(workerId);
            if (worker) {
                this.updateWorker(workerId, {
                    totalPoints: worker.totalPoints + task.rewardPoints,
                    monthlyPoints: worker.monthlyPoints + task.rewardPoints,
                    completedTasks: worker.completedTasks + 1
                });
            }

            // 統計更新
            const stats = this.getData('stats');
            this.saveData('stats', {
                ...stats,
                totalSentToday: stats.totalSentToday + 1,
                totalSentMonth: stats.totalSentMonth + 1
            });
        }

        return task;
    }

    // 統計
    getStats() {
        return this.getData('stats') || {
            totalSentToday: 0,
            totalSentMonth: 0,
            activeProjects: 0,
            activeWorkers: 0,
            pendingAIAnalysis: 0
        };
    }

    updateStats(updates) {
        const stats = this.getStats();
        this.saveData('stats', { ...stats, ...updates });
    }

    // ========================================
    // ユーティリティ
    // ========================================
    getNextId(array) {
        if (array.length === 0) return 1;
        return Math.max(...array.map(item => item.id)) + 1;
    }

    // CSV解析（簡易版）
    parseCSV(csvText) {
        const lines = csvText.split('\n').filter(line => line.trim());
        if (lines.length < 2) return [];

        const headers = lines[0].split(',').map(h => h.trim());
        const data = [];

        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim());
            const row = {};
            headers.forEach((header, index) => {
                row[header] = values[index] || '';
            });
            data.push(row);
        }

        return data;
    }

    // データエクスポート
    exportToCSV(data, filename) {
        if (data.length === 0) return;

        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(h => row[h] || '').join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    }

    // データリセット
    clearAllData() {
        const keys = ['companies', 'products', 'workers', 'projects', 'tasks', 'stats'];
        keys.forEach(key => localStorage.removeItem(`aiautoform_${key}`));
        localStorage.removeItem('aiautoform_initialized');
    }
}
