// Disable framework telemetry for every supported npm entry point, including development.
process.env.NEXT_TELEMETRY_DISABLED='1';
await import('next/dist/bin/next');
