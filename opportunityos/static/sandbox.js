document.querySelector("form").addEventListener("submit", event => {
  event.preventDefault();
  document.querySelector("#receipt").textContent = "LOCAL-TEST-" + crypto.randomUUID();
  event.target.querySelector("button").disabled = true;
});
