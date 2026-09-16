(() => {
  const cfg = window.RESTRICTED_CONFIG || {};
  const $ = (s) => document.querySelector(s);

  $("#year").textContent = new Date().getFullYear();

  // Join actions point to Discord. FiveM live status/player data below still uses Cfx.re.
  const discordUrl = cfg.discordUrl || "#";
  ["#playBtn", "#discordBtn", "#navJoin", "#joinPlayBtn"].forEach(sel => {
    const el = $(sel);
    if (el) el.href = discordUrl;
  });

  const menuToggle = $("#menuToggle"), nav = $("#nav");
  menuToggle?.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  nav?.querySelectorAll("a").forEach(a => a.addEventListener("click", () => nav.classList.remove("open")));

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in-view");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: .12 });
  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));


  // Back-to-top links: always scroll the current page all the way to the top.
  document.querySelectorAll(".back-top").forEach(link => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
    });
  });

  // Live FiveM server status/player count.
  // No custom endpoint or in-game FiveM resource is required. The site uses
  // the public Cfx.re server-list data for the configured server code.
  const CFX_API = "https://frontend.cfx-services.net/api/servers/single/";

  function extractServerData(payload) {
    // The Cfx response is normally wrapped in `Data`, but keeping these
    // fallbacks makes the website tolerant of small API response changes.
    const data = payload?.Data || payload?.data || payload || {};
    const players = Array.isArray(data.players)
      ? data.players
      : Array.isArray(data?.players?.list)
        ? data.players.list
        : [];

    const countCandidates = [
      data.clients,
      data.players?.count,
      data.players?.selfReported,
      data.players?.self_reported,
      players.length
    ];

    const count = countCandidates.find(v => Number.isFinite(Number(v)));
    const maxCandidates = [
      data.sv_maxclients,
      data.sv_maxClients,
      data.maxclients,
      data.slots,
      data.vars?.sv_maxClients
    ];
    const max = maxCandidates.find(v => Number.isFinite(Number(v)));

    return {
      count: count == null ? null : Number(count),
      max: max == null ? null : Number(max),
      hostname: data.hostname || data.vars?.sv_projectName || data.vars?.sv_hostname || "",
      players
    };
  }

  async function fetchLiveServer() {
    const code = String(cfg.serverCode || "").trim();
    if (!code) throw new Error("Missing server code");

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 7000);

    try {
      const url = `${CFX_API}${encodeURIComponent(code)}`;
      const res = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return extractServerData(await res.json());
    } finally {
      clearTimeout(timer);
    }
  }

  async function updateServer() {
    const status = $("#serverStatus"), heroStatus = $("#heroStatus");
    const count = $("#onlineCount"), heroPlayers = $("#heroPlayers");
    const last = $("#lastUpdate");

    try {
      const server = await fetchLiveServer();

      if (server.count == null) throw new Error("Player count unavailable");

      const formatted = server.max
        ? `${server.count.toLocaleString()} / ${server.max.toLocaleString()}`
        : server.count.toLocaleString();

      if (count) count.textContent = formatted;
      if (heroPlayers) heroPlayers.textContent = formatted;
      if (status) {
        status.textContent = "ONLINE";
        status.classList.add("ok");
      }
      if (heroStatus) {
        heroStatus.textContent = "ONLINE";
        heroStatus.classList.add("ok");
      }
      if (last) last.textContent = `Updated ${new Date().toLocaleTimeString()}`;

      // If the server has a name available, expose it for any future element
      // with the optional #serverName id without changing the current design.
      document.querySelectorAll("#serverName").forEach(el => {
        if (server.hostname) el.textContent = server.hostname;
      });
    } catch (error) {
      if (status) {
        status.textContent = "OFFLINE";
        status.classList.remove("ok");
      }
      if (heroStatus) {
        heroStatus.textContent = "OFFLINE";
        heroStatus.classList.remove("ok");
      }
      if (count) count.textContent = "—";
      if (heroPlayers) heroPlayers.textContent = "—";
      if (last) last.textContent = "Unable to reach Cfx.re";
      console.warn("RestrictedRP live server check failed:", error);
    }
  }

  updateServer();
  // Refresh frequently enough to feel live while avoiding excessive requests.
  setInterval(updateServer, 15000);

  const canvas = $("#particles"), ctx = canvas?.getContext("2d");
  if (canvas && ctx && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let ps = [], w = 0, h = 0;
    const resize = () => { w = canvas.width = innerWidth; h = canvas.height = innerHeight; };
    const make = () => ({ x: Math.random()*w, y: Math.random()*h, r: Math.random()*1.4+.3, vx:(Math.random()-.5)*.12, vy:(Math.random()-.5)*.12, a:Math.random()*.45+.08 });
    const init = () => { ps = Array.from({length: 55}, make); };
    resize(); init(); addEventListener("resize", () => { resize(); init(); });
    const draw = () => {
      ctx.clearRect(0,0,w,h);
      ps.forEach((p,i) => {
        p.x += p.vx; p.y += p.vy;
        if (p.x<0)p.x=w;if(p.x>w)p.x=0;if(p.y<0)p.y=h;if(p.y>h)p.y=0;
        ctx.beginPath(); ctx.fillStyle=`rgba(239,27,37,${p.a})`; ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fill();
        for(let j=i+1;j<ps.length;j++){
          const q=ps[j], dx=p.x-q.x, dy=p.y-q.y, d=Math.hypot(dx,dy);
          if(d<105){ctx.strokeStyle=`rgba(239,27,37,${(1-d/105)*.08})`;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();}
        }
      });
      requestAnimationFrame(draw);
    };
    draw();
  }
})();
