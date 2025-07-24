console.log('Discord bot container is running');
console.log('Environment:', process.env.NODE_ENV);
console.log('Redis URL:', process.env.REDIS_URL);

// Keep the process running
setInterval(() => {
  console.log('Bot heartbeat:', new Date().toISOString());
}, 30000);