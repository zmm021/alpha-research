
--🔥 设计说明（简要）
--	•	symbols：资产 registry（以后 macro 也能放）
--	•	sectors：板块定义（可扩展多个）
--	•	symbol_sector_map：多对多（未来一个股票可属于多个 theme）
CREATE TABLE symbols (
    symbol TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL,         -- stock / etf / index / commodity
    exchange TEXT,
    currency TEXT DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sectors (
    sector_id SERIAL PRIMARY KEY,
    sector_name TEXT UNIQUE NOT NULL,   -- e.g. rare_earth, tech
    description TEXT,
    benchmark_symbol TEXT,              -- optional (e.g. XLE / SMH)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE symbol_sector_map (
    symbol TEXT REFERENCES symbols(symbol),
    sector_id INT REFERENCES sectors(sector_id),
    weight NUMERIC DEFAULT 1.0,        -- optional future use
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    PRIMARY KEY (symbol, sector_id)
);
CREATE INDEX idx_symbol_sector ON symbol_sector_map(sector_id);

CREATE TABLE macro_groups (
    macro_group_id SERIAL PRIMARY KEY,
    macro_group_name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE symbol_macro_map (
    symbol TEXT REFERENCES symbols(symbol),
    macro_group_id INT REFERENCES macro_groups(macro_group_id),
    role TEXT NOT NULL,                  -- market_benchmark / risk_proxy / liquidity_proxy / commodity_proxy ...
    weight NUMERIC DEFAULT 1.0,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    PRIMARY KEY (symbol, macro_group_id, role)
);

INSERT INTO sectors (sector_name, description)
VALUES
    ('uranium', 'Uranium and nuclear fuel related companies');


INSERT INTO symbols (symbol, asset_type, exchange)
VALUES
    ('REMX', 'etf', 'NYSE')
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbol_sector_map (symbol, sector_id)
SELECT 'REMX', sector_id
FROM sectors
WHERE sector_name = 'rare_earth'
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.sectors TO trading_os;