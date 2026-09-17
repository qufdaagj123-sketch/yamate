document.querySelectorAll("a[href^='#']").forEach(a=>{
  a.addEventListener("click",()=>{
    document.querySelectorAll(".sidebar nav a").forEach(x=>x.classList.remove("active"));
    const target=a.getAttribute("href");
    const side=document.querySelector(`.sidebar nav a[href="${target}"]`);
    if(side) side.classList.add("active");
  });
});
document.querySelectorAll("form").forEach(f=>{
  f.addEventListener("submit",()=>{
    const b=f.querySelector("button[type='submit'],button:not([type])");
    if(b && !b.dataset.locked){b.dataset.locked="1";b.style.opacity=".65";b.textContent="Working…";}
  });
});
