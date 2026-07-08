#!/usr/bin/env python3
"""
Build-time injector for the PM evidence-check page.

The committed index.html is kept as the pristine, byte-for-byte source that
Andrew authors. This script runs during the GitHub Pages deploy (before the
artifact is uploaded) and adds reviewer-activity logging to the *deployed copy
only*, so:

  * the repo's index.html always matches Andrew's exact bytes, and
  * tracking can never be accidentally dropped when index.html is replaced.

It is idempotent: if the file already contains the tracking marker it is left
unchanged. Every transform is a plain string replace; if a target string is not
found (e.g. Andrew restructured the page) the script logs a warning and carries
on, so the live logging block is still injected.
"""

import sys

PATH = "index.html"
MARKER = "pm_evidence_events"  # presence => already injected

# --- The tracking block, inserted just before the page's closing </script> so
# --- it shares scope with the page's own store/KEY/totalItems/etc. -----------
TRACKING = r"""
/* ---- Reviewer activity logging (Supabase, insert-only) — injected at build - */
(function(){
  var SB_URL  = "https://zlwpywqxmvdxnyktnoia.supabase.co";
  var SB_KEY  = "sb_publishable_CE2I-Kf55SRDCfdgH3IZlA_g-LuSScM";
  var ENDPOINT = SB_URL + "/rest/v1/pm_evidence_events";

  var SID_KEY = "pm_evidence_check_sid", sid;
  try{ sid = localStorage.getItem(SID_KEY); }catch(e){}
  if(!sid){
    sid = (self.crypto && crypto.randomUUID) ? crypto.randomUUID()
        : "s-" + new Date().getTime() + "-" + Math.random().toString(36).slice(2);
    try{ localStorage.setItem(SID_KEY, sid); }catch(e){}
  }
  var t0 = new Date().getTime();

  function post(row){
    try{
      fetch(ENDPOINT, {
        method:"POST",
        headers:{ "apikey":SB_KEY, "Authorization":"Bearer "+SB_KEY,
                  "Content-Type":"application/json", "Prefer":"return=minimal" },
        body:JSON.stringify(row), keepalive:true, mode:"cors", credentials:"omit"
      }).catch(function(){});
    }catch(e){}
  }
  function splitKey(key){
    var i = (key||"").indexOf("::");
    return i>=0 ? { claim:key.slice(0,i), ref:key.slice(i+2) } : { claim:null, ref:(key||null) };
  }
  function nameDate(){
    var n=null,d=null;
    try{ if(typeof store!=="undefined"){ n=store.name||null; d=store.date||null; } }catch(e){}
    if(!n){ var en=document.getElementById("rev-name"); if(en) n=en.value.trim()||null; }
    if(!d){ var ed=document.getElementById("rev-date"); if(ed) d=ed.value.trim()||null; }
    return {n:n,d:d};
  }
  function reviewedCount(){
    var done=0;
    try{ Object.keys(store.recs).forEach(function(kk){ if(store.recs[kk] && store.recs[kk].support) done++; }); }catch(e){}
    return done;
  }
  function totalCount(){ try{ return totalItems(); }catch(e){ return 0; } }

  function track(type, opts){
    opts = opts || {};
    var nd = nameDate();
    var row = {
      session_id:sid, reviewer_name:nd.n, reviewer_date:nd.d, event_type:type,
      claim:opts.claim || null, paper_ref:opts.ref || null, detail:opts.detail || null,
      page_path:location.pathname, user_agent:navigator.userAgent
    };
    try{
      if(typeof store!=="undefined" && store){
        store.events = store.events || [];
        store.events.push({ t:new Date().toISOString(), type:type,
          claim:row.claim, ref:row.paper_ref, detail:row.detail });
        if(store.events.length > 3000) store.events.splice(0, store.events.length - 3000);
        try{ localStorage.setItem(KEY, JSON.stringify(store)); }catch(e){}
      }
    }catch(e){}
    post(row);
  }
  window.pmTrack = track;

  // expand / collapse
  if(typeof window.toggle === "function"){
    var _toggle = window.toggle;
    window.toggle = function(key){
      _toggle(key);
      var w = document.getElementById("wrap-"+key), s = splitKey(key);
      track(w && w.classList.contains("open") ? "expand" : "collapse", { claim:s.claim, ref:s.ref });
    };
  }
  // rating / judgement changes
  if(typeof window.pick === "function"){
    var _pick = window.pick;
    window.pick = function(key,q,val){
      _pick(key,q,val);
      var s = splitKey(key);
      track("rating", { claim:s.claim, ref:s.ref, detail:{ field:q, value:val } });
    };
  }
  // comments & rating-notes (blur / change)
  document.addEventListener("change", function(e){
    var el = e.target; if(!el || !el.matches) return;
    if(el.matches("textarea[data-c]")){
      var s = splitKey(el.getAttribute("data-c"));
      track("comment", { claim:s.claim, ref:s.ref,
        detail:{ length:el.value.trim().length, text:el.value.trim().slice(0,2000) } });
    } else if(el.matches("input[data-ro]")){
      var s2 = splitKey(el.getAttribute("data-ro"));
      track("rating_note", { claim:s2.claim, ref:s2.ref, detail:{ text:el.value.trim().slice(0,500) } });
    }
  }, true);
  // journal source click-throughs
  document.addEventListener("click", function(e){
    var a = e.target && e.target.closest ? e.target.closest('a[target="_blank"]') : null;
    if(!a) return;
    var href = a.getAttribute("href") || "";
    if(!/^https?:/i.test(href)) return;
    var wrap = a.closest ? a.closest(".paper") : null;
    var key = wrap ? (wrap.id||"").replace(/^wrap-/, "") : "";
    var s = key ? splitKey(key) : { claim:null, ref:null };
    track("source_click", { claim:s.claim, ref:s.ref,
      detail:{ url:href, label:(a.textContent||"").replace(/\s+/g," ").trim().slice(0,120) } });
  }, true);
  // completion — fire once when every item reviewed (DOM-based, store-independent)
  var _completed = false;
  function checkComplete(){
    var total = totalCount(), done = reviewedCount();
    if(!_completed && total>0 && done>=total){ _completed = true; track("completion", { detail:{ reviewed:done, total:total } }); }
  }
  if(typeof window.updateProgress === "function"){
    var _up = window.updateProgress;
    window.updateProgress = function(){ _up(); checkComplete(); };
  }
  // explicit export / finish
  if(typeof window.exportLog === "function"){
    var _export = window.exportLog;
    window.exportLog = function(){ track("export", null); return _export.apply(this, arguments); };
  }
  // session lifecycle
  track("session_start", { detail:{ referrer:document.referrer||null, screen:(screen.width+"x"+screen.height) } });
  document.addEventListener("visibilitychange", function(){
    track(document.visibilityState==="hidden" ? "hidden" : "visible",
      { detail:{ seconds:Math.round((new Date().getTime()-t0)/1000) } });
  });
  var _endSent = false;
  window.addEventListener("pagehide", function(){
    if(_endSent) return; _endSent = true;
    track("session_end", { detail:{ seconds:Math.round((new Date().getTime()-t0)/1000),
      reviewed:reviewedCount(), total:totalCount() } });
  });
  checkComplete();
})();
"""

# --- Idempotent transforms to also embed the event trail in the JSON export --
EDITS = [
    ("let store = { name:\"\", date:\"\", recs:{} };",
     "let store = { name:\"\", date:\"\", recs:{}, events:[] };"),
    ("store = s; store.recs = s.recs || {};",
     "store = s; store.recs = s.recs || {}; store.events = s.events || [];"),
    ("    claims:claims, content_decision_items:content\n  };",
     "    claims:claims, content_decision_items:content,\n    activity_events:(store.events||[])\n  };"),
    ("  store = { name:\"\", date:\"\", recs:{} };\n  location.reload();",
     "  store = { name:\"\", date:\"\", recs:{}, events:[] };\n  location.reload();"),
]


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        html = f.read()

    if MARKER in html:
        print("inject_tracking: marker already present; leaving file unchanged.")
        return

    for old, new in EDITS:
        if old in html:
            html = html.replace(old, new, 1)
        else:
            print("inject_tracking: WARNING target not found (export-enrichment skipped): "
                  + old[:60].replace("\n", " ") + "...", file=sys.stderr)

    idx = html.rfind("</script>")
    if idx == -1:
        print("inject_tracking: ERROR no </script> found; cannot inject tracking.", file=sys.stderr)
        sys.exit(1)
    html = html[:idx] + "\n" + TRACKING + "\n" + html[idx:]

    with open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("inject_tracking: tracking injected into deployed copy of index.html.")


if __name__ == "__main__":
    main()
