"use strict";
console.log('Discord bot container is running');
console.log('Environment:', process.env.NODE_ENV);
console.log('Redis URL:', process.env.REDIS_URL);
setInterval(() => {
    console.log('Bot heartbeat:', new Date().toISOString());
}, 30000);
//# sourceMappingURL=test.js.map