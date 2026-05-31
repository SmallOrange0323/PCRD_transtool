console.log("events.js loaded");
/**
 * PCR 台版數據導航站 - 活動頁面
 * 負責渲染進行中與預告活動
 */

window.EventsModule = {
    async render() {
        const container = document.getElementById('events-tab');
        container.innerHTML = '<div class="loading-mini">讀取活動數據中...</div>';

        try {
            // 1. 取得活動列表
            const allEvents = window.PCRDatabase.runQuery(`
                SELECT
                    event.event_id,
                    event.start_time,
                    event.end_time,
                    COALESCE(c.title, '特殊活動') AS title
                FROM (
                    SELECT a.event_id, a.start_time, a.end_time
                    FROM hatsune_schedule AS a
                    UNION
                    SELECT b.event_id, b.start_time, b.end_time
                    FROM shiori_event_list AS b
                ) AS event
                LEFT JOIN event_story_data AS c ON c.story_group_id = (event.event_id % 10000 + 5000)
                ORDER BY event.start_time DESC
                LIMIT 50
            `);

            // 2. 取得加倍活動
            const campaigns = window.PCRDatabase.runQuery(`
                SELECT campaign_category, value, start_time, end_time
                FROM campaign_schedule
                WHERE lv_to = -1
                ORDER BY start_time DESC
                LIMIT 30
            `);

            this.renderLayout(container, allEvents, campaigns);
        } catch (error) {
            container.innerHTML = `<div class="error-box">活動數據加載失敗: ${error.message}</div>`;
        }
    },

    renderLayout(container, events, campaigns) {
        const now = this.getRegionTime();
        
        // 合併並分類
        const processedEvents = this.processEvents(events, campaigns, now);
        
        container.innerHTML = `
            <div class="event-section">
                <h2 class="section-title"><span class="icon">📡</span> 進行中的活動 (${window.PCRDatabase.currentRegion.toUpperCase()})</h2>
                <div class="event-list">
                    ${processedEvents.ongoing.length ? processedEvents.ongoing.map(e => this.renderEventCard(e, 'ongoing', now)).join('') : '<div class="empty-msg">目前沒有進行中的活動</div>'}
                </div>
            </div>

            <div class="event-section">
                <h2 class="section-title"><span class="icon">📅</span> 即將到來的活動</h2>
                <div class="event-list">
                    ${processedEvents.upcoming.length ? processedEvents.upcoming.map(e => this.renderEventCard(e, 'upcoming', now)).join('') : '<div class="empty-msg">目前沒有預告活動</div>'}
                </div>
            </div>
        `;
    },

    processEvents(events, campaigns, now) {
        const ongoing = [];
        const upcoming = [];

        const all = [...events.map(e => ({ ...e, type: 'story' })), 
                    ...campaigns.map(c => ({ 
                        title: this.getCampaignTitle(c.campaign_category, c.value), 
                        start_time: c.start_time, 
                        end_time: c.end_time, 
                        type: 'campaign' 
                    }))];

        all.forEach(e => {
            const start = new Date(e.start_time.replace(/\//g, '-'));
            const end = new Date(e.end_time.replace(/\//g, '-'));

            if (now >= start && now <= end) {
                ongoing.push({ ...e, start, end });
            } else if (now < start) {
                // 僅顯示 60 天內的預告
                if (start - now < 60 * 24 * 60 * 60 * 1000) {
                    upcoming.push({ ...e, start, end });
                }
            }
        });

        // 排序：進行中的按結束時間排序（快結束的在前），預告的按開始時間排序（快開始的在前）
        ongoing.sort((a, b) => a.end - b.end);
        upcoming.sort((a, b) => a.start - b.start);

        return { ongoing, upcoming };
    },

    renderEventCard(event, status, now) {
        const isOngoing = status === 'ongoing';
        const targetDate = isOngoing ? event.end : event.start;
        const diff = targetDate - now;
        
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        const hours = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
        
        let countdownStr = '';
        if (days > 0) countdownStr = `${days} 天 ${hours} 小時`;
        else if (hours > 0) countdownStr = `${hours} 小時`;
        else countdownStr = `即將${isOngoing ? '結束' : '開始'}`;

        return `
            <div class="event-card glass-card ${event.type}">
                <div class="event-info">
                    <div class="event-title">${event.title}</div>
                    <div class="event-time">${event.start_time.split(' ')[0]} ~ ${event.end_time.split(' ')[0]}</div>
                </div>
                <div class="event-status ${status}">
                    <div class="status-label">${isOngoing ? '剩餘' : '倒數'}</div>
                    <div class="status-value">${countdownStr}</div>
                </div>
            </div>
        `;
    },

    getRegionTime() {
        const now = new Date();
        // 台版 UTC+8, 日版 UTC+9
        const offset = window.PCRDatabase.currentRegion === 'jp' ? 9 : 8;
        const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        return new Date(utc + (3600000 * offset));
    },

    getCampaignTitle(category, value) {
        const names = {
            31: '普通關卡 (Normal) 掉落量',
            32: '困難關卡 (Hard) 掉落量',
            34: '探索 (Quest) 掉落量',
            37: '聖跡調查 掉落量',
            38: '神殿調查 掉落量',
            39: '高難度關卡 (Very Hard) 掉落量',
            41: '普通關卡 (Normal) 瑪那',
            42: '困難關卡 (Hard) 瑪那',
            45: '地下城 (Dungeon) 瑪那',
            49: '高難度關卡 (Very Hard) 瑪那'
        };
        const multiplier = (value / 100).toFixed(1);
        return `${names[category] || '加倍活動'} ${multiplier}x`;
    }
};
