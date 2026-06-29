-- Grants for pipeline roles (local dev uses single netpulse user)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO netpulse;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO netpulse;
GRANT ALL PRIVILEGES ON SCHEMA staging TO netpulse;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging TO netpulse;
