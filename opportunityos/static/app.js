"use strict";
const $ = (q) => document.querySelector(q);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const url = (value) => { try { return new URL(value).protocol === "https:" ? esc(value) : "#"; } catch { return "#"; } };
const sections = {"Dashboard":"◫","Discover":"⌕","Applications":"▤","Review Center":"◇","Profile":"◎","Agent Activity":"≋","Settings":"⚙"};
const label = (key) => key.replaceAll("_", " ");
let page = "Dashboard", data, selected, timer;
const filter = {q:"", group:"", pay:false, hidden:false};
const empty = (text) => '<p class="empty">' + esc(text) + '</p>';
const heading = (title, sub) => '<div class="eyebrow">PERSONAL OPPORTUNITY DESK</div><h1>' + esc(title) + '</h1><p class="muted">' + esc(sub) + '</p>';
const link = (href, title) => '<a target="_blank" rel="noopener noreferrer" href="' + url(href) + '">' + esc(title) + '</a>';
function flash(message) {
  $("#toast").textContent = message;
  clearTimeout(timer);
  timer = setTimeout(() => $("#toast").textContent = "", 5000);
}
async function load() {
  const response = await fetch("/api/state");
  if (!response.ok) throw Error("Local workspace is unavailable");
  data = await response.json();
  renderAgent(data.agent);
}
function renderAgent(state) {
  $("#agent-status").textContent = state;
  $("#run").textContent = state === "Paused" ? "▶ Resume" : "▶ Run now";
  $("#run").disabled = ["Running","Stopping"].includes(state);
  $("#pause").disabled = state !== "Running";
  $("#stop").disabled = ["Stopped","Stopping"].includes(state);
}
async function mutate(path, body, message) {
  const response = await fetch("/api/" + path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error);
  await load();
  if (message) flash(message);
  render();
}
function card(item) {
  return '<article class="card"><div class="card-top"><span class="chip">' + esc(item.group) +
    '</span><span class="score" title="Recommendation score">' + item.score + '</span></div><h3>' + esc(item.title) +
    '</h3><span class="muted">' + esc(item.organization + " · " + item.location) + '</span><p>' + esc(item.matches.join(" · ") || item.category) +
    '</p><button data-detail="' + esc(item.id) + '">View evidence →</button></article>';
}
const active = () => data.items.filter(i => i.state === "Listed" && i.eligibility !== "Ineligible");
const review = () => data.apps.filter(a => a.status === "Awaiting review");
function dashboard() {
  const picks = active().slice(0,6);
  return '<section class="hero"><div class="eyebrow">YOUR LOCAL OPPORTUNITY AGENT</div><h1>Find your next<br>opening.</h1><p>Discover early-career opportunities and prepare your strongest applications.</p></section>' +
    '<div class="metrics">' + [[active().length,"Current leads"],[review().length,"Awaiting review"],[data.health.filter(h=>h.status==="OK").length,"Healthy sources"]].map(([n,t])=>'<div class="metric"><b>'+n+'</b><span>'+t+'</span></div>').join("") +
    '</div><div class="section"><h2>Recommended for you</h2><button data-nav="Discover">Explore feed →</button></div>' +
    (picks.length ? '<div class="grid">'+picks.map(card).join("")+'</div>' : empty("Run discovery to check the official sources.")) +
    '<div class="section"><h2>Recent activity</h2><button data-nav="Agent Activity">Open activity</button></div>' + activity(data.activity.slice(0,3));
}
function listings() {
  const hits = (filter.hidden ? data.items : active()).filter(i =>
    (!filter.group || i.group === filter.group) && (!filter.pay || i.funding !== "Unknown") &&
    [i.title,i.organization,i.location,...i.matches].join(" ").toLowerCase().includes(filter.q.toLowerCase()));
  $("#listings").innerHTML = '<p class="muted">' + hits.length + ' opportunities</p>' +
    (hits.length ? '<div class="grid">'+hits.map(card).join("")+'</div>' : empty("No opportunities match these filters."));
}
function discover() {
  const groups = [...new Set(data.items.map(i=>i.group))].sort();
  return heading("Discover","Live employer listings ranked for your profile. Open a listing to check the evidence.") +
    '<div class="toolbar"><input id="search" type="search" aria-label="Search opportunities" placeholder="Search role, company or location" value="' + esc(filter.q) +
    '"><select id="group" aria-label="Recommendation group"><option value="">All groups</option>' +
    groups.map(g=>'<option'+(g===filter.group?' selected':'')+'>'+esc(g)+'</option>').join("") +
    '</select><label><input type="checkbox" id="pay" '+(filter.pay?'checked':'')+'> Pay disclosed</label><label><input type="checkbox" id="hidden" '+(filter.hidden?'checked':'')+'> Include unlisted and ineligible</label></div><div id="listings"></div>';
}
function showDetail(id) {
  selected = data.items.find(i=>i.id===id);
  const i = selected;
  const existing = data.apps.find(a=>a.opportunity===id);
  $("#detail-body").innerHTML = '<div class="eyebrow">'+esc(i.organization+" · "+i.category)+'</div><h2 id="detail-title">'+esc(i.title)+'</h2>' +
    '<p><span class="chip">'+esc(i.state+" · "+i.eligibility)+'</span> <strong>'+i.score+' / 100</strong></p><p>'+esc(i.reason)+
    ' '+esc(i.matches.length ? "Matches: "+i.matches.join(", ")+".":"")+'</p><p><strong>Verify:</strong> '+esc(i.unknown.join("; "))+'</p><p><strong>Deadline:</strong> '+esc(i.deadline || "Unknown")+' · <strong>Location:</strong> '+esc(i.location)+
    '</p><p><strong>Pay evidence:</strong> '+esc(i.funding)+'</p><p>'+link(i.url,"Open official listing")+" · "+link(i.evidence,"Source feed")+" · Checked "+esc(i.checked.slice(0,10))+'</p><details><summary>Employer description</summary><pre class="description">'+esc(i.description)+'</pre></details>' +
    '<p><button id="inspect-form">Check portal questions</button></p><div id="portal-questions"></div>' +
    (existing ? '<p><button data-nav="Applications">Open existing application</button></p>' : i.state !== "Listed" || i.eligibility === "Ineligible" ? "" :
      '<form id="draft-form" class="stack"><label>Application question (optional)<textarea name="prompt" maxlength="5000" placeholder="Paste the actual question when available"></textarea></label><label>Word limit <input name="words" type="number" min="1" max="1200" value="250" required></label><button class="primary">Prepare draft for review</button></form>');
  $("#detail").showModal();
}
function application(a) {
  const i = data.items.find(item=>item.id===a.opportunity);
  const fieldList = Object.entries(a.fields).map(([key,value])=>'<li>'+esc(label(key)+": "+value)+'</li>').join("");
  const actions = [];
  if (a.status === "Awaiting review") actions.push(["ready","Mark ready"]);
  if (["Submitted","Awaiting response","Interview","Selected"].includes(a.status)) {
    for (const status of ["Awaiting response","Interview","Selected"]) if (status !== a.status) actions.push([status,status]);
  }
  actions.push(a.status==="Archived" ? ["restore","Restore"] : ["archive","Move to archive"]);
  return '<details class="box" data-app="'+esc(a.opportunity)+'"><summary>'+esc(i.title)+' <span class="chip">'+esc(a.status)+'</span></summary><p>'+link(i.url,"Open official listing")+' · '+esc(a.method)+'</p>' +
    (a.missing.length ? '<p class="muted">Unmapped standard fields: '+esc(a.missing.map(label).join(", "))+'</p>' : "") +
    (fieldList ? '<ul>'+fieldList+'</ul>' : "") +
    (a.prompt ? '<p><strong>Original question · '+a.words+' words</strong></p><pre>'+esc(a.prompt)+'</pre>' : "") +
    (["Awaiting review","Ready"].includes(a.status) ? '<form data-action="save"><label>Draft<textarea name="draft" maxlength="16000">'+esc(a.draft)+'</textarea></label><button>Save draft</button></form>' : '<pre>'+esc(a.draft)+'</pre>') +
    (a.status==="Ready" ? '<form data-action="submitted"><label>Portal confirmation or receipt <input name="evidence" required maxlength="2000"></label><button>Record manual submission</button></form>' : "") +
    (a.evidence ? '<p>Recorded evidence: '+esc(a.evidence)+'</p>' : "") +
    '<div class="row actions">'+actions.map(([action,title])=>'<button data-action="'+esc(action)+'">'+esc(title)+'</button>').join("")+'</div></details>';
}
function apps(onlyReview) {
  const items = onlyReview ? review() : data.apps.filter(a=>a.status!=="Archived");
  const archived = data.apps.filter(a=>a.status==="Archived");
  return heading(onlyReview?"Review Center":"Applications",onlyReview?"Check claims, requirements and word limits before marking a draft ready.":"Track prepared applications and record confirmed outcomes.") +
    (items.length ? '<div class="stack">'+items.map(application).join("")+'</div>' : empty(onlyReview?"No drafts awaiting review.":"No active applications.")) +
    (!onlyReview && data.mail.length ? '<div class="section"><h2>Gmail signals</h2></div><div class="stack">'+
      data.mail.map(m=>'<div class="box"><span class="chip">'+esc(m.kind)+'</span> '+esc(m.subject)+'</div>').join("")+'</div>' : "") +
    (!onlyReview && archived.length ? '<div class="section"><h2>Quiet archive</h2></div><div class="stack">'+archived.map(application).join("")+'</div>' : "");
}
function profile() {
  const fields = Object.values(data.facts).map(f=>'<details class="box"><summary>'+esc(label(f.key))+' <span class="chip">'+(f.verified?"Verified":f.value?"Unverified":"Missing")+'</span></summary><form data-fact="'+esc(f.key)+'"><label>Value<textarea name="value" maxlength="5000">'+esc(f.value)+'</textarea></label><label>Source <input name="source" value="'+esc(f.source)+'" maxlength="300"></label><label><input type="checkbox" name="verified" '+(f.verified?"checked":"")+'> I verified this fact</label><label><input type="checkbox" name="share" '+(f.share?"checked":"")+'> May be shared automatically when supported</label><button>Save fact</button></form></details>');
  return heading("Profile","Review seeded facts and add only details you can verify.") +
    '<div class="section"><h2>Document library</h2></div><div class="box"><form id="document-form"><label>Import PDF, DOCX or text (up to 10 MB)<input type="file" name="file" accept=".pdf,.docx,.txt" required></label><button>Import locally</button></form>' +
    data.documents.map(d=>'<p>'+esc(d.name)+' <span class="muted">'+Math.ceil(d.size/1024)+' KB</span></p>').join("")+
    '</div><div class="section"><h2>Personal facts</h2></div><div class="stack">'+fields.join("")+'</div>';
}
function activity(rows) {
  return rows.length ? '<div class="stack">'+rows.map(r=>'<div class="box"><span class="muted">'+esc(new Date(r.at).toLocaleString("en-HK",{timeZone:"Asia/Hong_Kong"}))+'</span> · '+esc(r.message)+'</div>').join("")+'</div>' : empty("No activity yet.");
}
function settings() {
  const s = data.settings;
  return heading("Settings","Configure discovery, ranking and optional local drafting.")+'<div class="box"><form id="settings-form">'+
    '<h2>Working window · Hong Kong</h2><div class="row">'+["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d,n)=>'<label><input type="checkbox" name="days" value="'+n+'" '+(s.days.includes(n)?"checked":"")+'> '+d+'</label>').join("")+'</div>'+
    '<div class="row"><label>Starts <input name="start" type="time" value="'+esc(s.start)+'" required></label><label>Ends <input name="end" type="time" value="'+esc(s.end)+'" required></label></div>'+
    '<label><input name="ac_only" type="checkbox" '+(s.ac_only?"checked":"")+'> Run on AC power only</label><h2>Official employer boards</h2><div class="row">'+
    Object.entries(data.sources).map(([k,v])=>'<label><input type="checkbox" name="sources" value="'+esc(k)+'" '+(s.enabled_sources.includes(k)?"checked":"")+'> '+esc(v)+'</label>').join("")+
    '</div><h2>Ranking weights</h2><div class="form-grid">'+Object.entries(s.weights).map(([k,v])=>'<label>'+esc(label(k))+' <input type="number" min="0" max="100" required name="'+esc(k)+'" value="'+v+'"></label>').join("")+
    '</div><h2>Drafting</h2><label>Ollama model (optional)<input name="ollama_model" maxlength="100" value="'+esc(s.ollama_model)+'" placeholder="Installed local model"></label><label>Essay style and instructions<textarea name="essay_style" maxlength="2000">'+esc(s.essay_style)+'</textarea></label><button class="primary">Save settings</button></form></div>';
}
function render() {
  const openApps = [...document.querySelectorAll("[data-app][open]")].map(el=>el.dataset.app);
  $("#nav").innerHTML = Object.entries(sections).map(([name,icon])=>'<button class="'+(name===page?"active":"")+'" data-nav="'+name+'"><span>'+icon+'</span>'+name+'</button>').join("");
  $("#crumb").textContent = "Workspace / " + page;
  $("#content").innerHTML = ({"Dashboard":dashboard,"Discover":discover,"Applications":()=>apps(false),"Review Center":()=>apps(true),
    "Profile":profile,"Agent Activity":()=>heading("Agent Activity","Source health and a local history of agent actions.")+
      '<div class="row">'+data.health.map(h=>'<span class="chip">'+esc(data.sources[h.source]+" · "+h.status+" · "+h.count)+'</span>').join("")+
      '</div><div class="section"><h2>Run history</h2></div>'+activity(data.activity),"Settings":settings})[page]();
  if (page==="Discover") listings();
  for (const el of document.querySelectorAll("[data-app]")) el.open=openApps.includes(el.dataset.app);
}
document.addEventListener("click", async e => {
  const b = e.target.closest("button");
  if (!b || b.disabled) return;
  try {
    if (b.dataset.nav) {
      $("#detail").close();
      page=b.dataset.nav; await load(); render(); window.scrollTo(0,0);
    } else if (b.dataset.detail) showDetail(b.dataset.detail);
    else if (b.id === "inspect-form") {
      const id = selected.id;
      b.disabled = true;
      try {
        const response = await fetch("/api/form",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
        const result = await response.json();
        if (!response.ok) throw Error(result.error);
        if (selected.id !== id) return;
        $("#portal-questions").innerHTML = result.questions.length ?
          '<ul>'+result.questions.map(q=>'<li>'+esc(q.label || q.group)+(q.required?' · Required':'')+
            (q.types.length?' · '+esc(q.types.join(", ")):'')+'</li>').join("")+'</ul>' :
          empty("The public API returned no questions. Check the official portal.");
      } finally { b.disabled = false; }
    }
    else if (b.dataset.action) await mutate("application",{id:b.closest("[data-app]").dataset.app,action:b.dataset.action},"Application updated");
    else if (["run","pause","stop"].includes(b.id)) await mutate("agent",{action:b.id});
  } catch (error) { flash(error.message); }
});
document.addEventListener("input", e=>{
  const keys={search:"q",group:"group",pay:"pay",hidden:"hidden"};
  if (keys[e.target.id]) { filter[keys[e.target.id]]=e.target.type==="checkbox"?e.target.checked:e.target.value; listings(); }
});
document.addEventListener("submit", async e=>{
  const f=e.target;
  if (f.method==="dialog") return;
  e.preventDefault();
  const v=new FormData(f);
  const button=f.querySelector("button");
  button.disabled=true;
  try {
    if (f.id==="draft-form") {
      await mutate("draft",{id:selected.id,prompt:v.get("prompt"),words:Number(v.get("words"))},"Draft placed in the Review Center");
      $("#detail").close(); page="Review Center"; render();
    } else if (f.dataset.action) await mutate("application",{...Object.fromEntries(v),id:f.closest("[data-app]").dataset.app,action:f.dataset.action},"Application updated");
    else if (f.dataset.fact) await mutate("fact",{key:f.dataset.fact,value:v.get("value"),source:v.get("source"),verified:v.has("verified"),share:v.has("share")},"Profile saved");
    else if (f.id==="settings-form") await mutate("settings",{...Object.fromEntries(v),ac_only:v.has("ac_only"),days:v.getAll("days").map(Number),
      enabled_sources:v.getAll("sources"),weights:Object.fromEntries(Object.keys(data.settings.weights).map(k=>[k,Number(v.get(k))]))},"Settings saved");
    else if (f.id==="document-form") {
      const file=v.get("file");
      if (!file.size || file.size>10000000) throw Error("Choose a document up to 10 MB");
      const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=reject;r.readAsDataURL(file);});
      await mutate("document",{name:file.name,content:encoded},"Document imported");
    }
  } catch (error) { flash(error.message); }
  finally { button.disabled=false; }
});
$("#theme").onclick=()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==="dark"?"light":"dark";localStorage.setItem("theme",root.dataset.theme);};
document.documentElement.dataset.theme=localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");
load().then(render).catch(e=>flash(e.message));
setInterval(async () => {
  try {
    const response = await fetch("/api/heartbeat");
    if (!response.ok) return;
    const {agent, revision} = await response.json();
    renderAgent(agent);
    if (["Dashboard","Agent Activity"].includes(page) && data?.revision !== revision) {
      await load();
      render();
    }
  } catch {}
}, 3500);
