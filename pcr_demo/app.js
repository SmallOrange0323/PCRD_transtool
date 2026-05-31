const API_URL = 'https://wthee.xyz/pcr/api/v1/db/info/v2';
const REGION = 'tw';

// 模擬的角色數據 (當無法連結真實 DB 時顯示)
const MOCK_UNITS = [
    { name: '佩可莉姆', icon: '🍙' },
    { name: '可可蘿', icon: '🌿' },
    { name: '凱留', icon: '🐱' },
    { name: '優衣', icon: '🌸' },
    { name: '日和', icon: '🐾' },
    { name: '怜', icon: '🗡️' }
];

async function fetchStatus() {
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ regionCode: REGION })
        });

        if (!response.ok) throw new Error('Network response was not ok');
        
        const result = await response.json();
        if (result.status === 0) {
            updateUI(result.data);
        }
    } catch (error) {
        console.error('Fetch error:', error);
        // 如果 API 失敗（可能是 CORS），顯示預設/錯誤狀態
        document.getElementById('version-val').innerText = '10053000';
        document.getElementById('time-val').innerText = '2024-04-23';
        document.getElementById('hash-val').innerText = 'D7F9972...';
        
        document.getElementById('version-val').classList.remove('loading-spinner');
        document.getElementById('time-val').classList.remove('loading-spinner');
        document.getElementById('hash-val').classList.remove('loading-spinner');
    }
}

function updateUI(data) {
    const versionEl = document.getElementById('version-val');
    const timeEl = document.getElementById('time-val');
    const hashEl = document.getElementById('hash-val');

    versionEl.innerText = data.truthVersion;
    timeEl.innerText = data.time.split(' ')[0];
    hashEl.innerText = data.hash.substring(0, 8).toUpperCase() + '...';

    versionEl.classList.remove('loading-spinner');
    timeEl.classList.remove('loading-spinner');
    hashEl.classList.remove('loading-spinner');
}

function renderMockUnits() {
    const container = document.getElementById('unit-results');
    container.innerHTML = '';
    
    MOCK_UNITS.forEach(unit => {
        const card = document.createElement('div');
        card.className = 'unit-card';
        card.innerHTML = `
            <div class="unit-icon">${unit.icon}</div>
            <div class="unit-name">${unit.name}</div>
        `;
        container.appendChild(card);
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    renderMockUnits();

    document.getElementById('search-btn').addEventListener('click', () => {
        const query = document.getElementById('unit-search').value;
        if (query) {
            alert(`在整合環境中，這將會執行 SQL 查詢：\nSELECT * FROM unit_data WHERE unit_name LIKE '%${query}%'`);
        }
    });
});
