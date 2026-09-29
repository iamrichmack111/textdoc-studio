const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: {
    baseURL: process.env.BASE_URL || 'http://family.local:8011',
    headless: true,
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 }
  }
});
