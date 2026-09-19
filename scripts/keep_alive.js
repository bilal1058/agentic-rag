const { chromium } = require("playwright");

(async () => {
  console.log("🚀 Launching headless Chromium browser session...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();

  console.log("📡 Visiting https://agentic-rag-chat.streamlit.app/ ...");
  try {
    // Navigate and wait for network traffic
    await page.goto("https://agentic-rag-chat.streamlit.app/", {
      waitUntil: "networkidle",
      timeout: 60000,
    });

    // Check if the app is in sleep mode
    const wakeBtn = await page.$(
      'button:has-text("Yes, get this app back up!")'
    );
    if (wakeBtn) {
      console.log('⚠️ App was asleep. Waking it up: clicking "Yes, get this app back up!"...');
      await wakeBtn.click();
      console.log("⏳ Waiting for container to spin up...");
      await page.waitForSelector('[data-testid="stAppViewContainer"]', {
        timeout: 90000,
      });
      console.log("✨ Container successfully spun up!");
    } else {
      console.log("✅ App is already awake! Connecting active viewer session...");
      // Wait for Streamlit core DOM and WebSocket connection to be fully live
      await page.waitForSelector(
        '[data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"], #auth-welcome-container',
        { timeout: 45000 }
      );
    }

    // Keep the live session open for 25 seconds so Streamlit backend registers real viewer telemetry
    console.log("⏱️ Holding active WebSocket session for 25 seconds to register live user activity...");
    await page.waitForTimeout(25000);
    console.log("🎯 Live session successfully registered with Streamlit Cloud. Idle timer reset!");
  } catch (err) {
    console.log("Session notice:", err.message);
  } finally {
    await browser.close();
    console.log("🏁 Keep-alive cycle completed.");
  }
})();
