CREATE TABLE meta_symbol_offset (
    symbol TEXT PRIMARY KEY REFERENCES symbols(symbol),
    offset_date DATE NOT NULL,  
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.meta_symbol_offset TO trading_os;