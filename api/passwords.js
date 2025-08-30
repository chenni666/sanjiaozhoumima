// Serverless function for Vercel: returns passwords from output/mima_data.json
// Response shape: [{ name, password, date }]

const fs = require('node:fs/promises');
const path = require('node:path');

const DATA_PATH = path.join(process.cwd(), 'output', 'mima_data.json');

function mapRecord(rec) {
  // Source keys are Chinese: 名称 / 密码 / 日期
  return {
    name: String(rec && rec['名称'] ? rec['名称'] : ''),
    password: String(rec && rec['密码'] ? rec['密码'] : ''),
    date: String(rec && rec['日期'] ? rec['日期'] : ''),
  };
}

function fallbackData() {
  // Lightweight fallback aligned with the static placeholders from index.html
  return [
    { name: '零号大坝', password: '8699', date: '2025-08-28' },
    { name: '长弓溪谷', password: '0465', date: '2025-08-28' },
    { name: '巴克什', password: '2109', date: '2025-08-28' },
    { name: '航天基地', password: '8861', date: '2025-08-28' },
    { name: '潮汐监狱', password: '2548', date: '2025-08-28' },
  ];
}

module.exports = async function handler(req, res) {
  try {
    const file = await fs.readFile(DATA_PATH, 'utf8');
    const json = JSON.parse(file);
    const list = Array.isArray(json) ? json.map(mapRecord) : [];
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300');
    return res.status(200).json(list.length ? list : fallbackData());
  } catch (err) {
    // Fallback to static sample if file not found or invalid JSON
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json(fallbackData());
  }
};
