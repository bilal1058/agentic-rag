const { chromium } = require("playwright");

(async () => {
  console.log("Launching headless browser...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();

  console.log("Navigating to https://agentic-rag-chat.streamlit.app/ ...");
  try {
    await page.goto("https://agentic-rag-chat.streamlit.app/", {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await page.waitForTimeout(6000);

    // Look for the Streamlit sleeping screen button
    const wakeBtn = await page.$(
      'button:has-text("Yes, get this app back up!")'
    );
    if (wakeBtn) {
      console.log('🚨 App was sleeping! Clicking "Yes, get this app back up!"...');
      await wakeBtn.click();
      console.log("Wake-up button clicked! Waiting 15s for container spin-up...");
      await page.waitForTimeout(15000);
      console.log("Wake-up cycle complete!");
    } else {
      console.log("✅ App is already awake and actively serving sessions.");
    }
  } catch (err) {
    console.log("Notice during navigation:", err.message);
  } finally {
    await browser.close();
  }
})();
