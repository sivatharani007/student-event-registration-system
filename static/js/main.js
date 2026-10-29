(function () {
  "use strict";

  // Loading state on submit buttons (prevents double submission).
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented) { return; }
    var button = form.querySelector("button[data-loading]");
    if (button) {
      window.setTimeout(function () {
        button.disabled = true;
        button.classList.add("is-loading");
        button.insertAdjacentHTML("afterbegin", '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>');
      }, 0);
    }
  });

  // Restore buttons if the user comes back with the browser Back button.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) { return; }
    document.querySelectorAll("button[data-loading]").forEach(function (b) {
      b.disabled = false;
      b.classList.remove("is-loading");
      var spinner = b.querySelector(".spinner-border");
      if (spinner) { spinner.remove(); }
    });
  });

  // Confirm dangerous actions (cancel registration, delete event).
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) { event.preventDefault(); }
    });
  });

  // Password match check (the server validates again).
  document.querySelectorAll("form[data-validate-passwords]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var pw = form.querySelector("#password");
      var confirmPw = form.querySelector("#confirm_password");
      if (pw && confirmPw && pw.value !== confirmPw.value) {
        event.preventDefault();
        confirmPw.setCustomValidity("Passwords do not match.");
        confirmPw.reportValidity();
        confirmPw.addEventListener("input", function () { confirmPw.setCustomValidity(""); }, { once: true });
      }
    });
  });

  // Recommendation form: at least one interest.
  var recForm = document.getElementById("rec-form");
  if (recForm) {
    recForm.addEventListener("submit", function (event) {
      if (!recForm.querySelector('input[name="interests"]:checked')) {
        event.preventDefault();
        window.alert("Please select at least one interest.");
      }
    });
  }

  // Auto-dismiss success/info messages after a few seconds.
  window.setTimeout(function () {
    document.querySelectorAll("#flash-area .alert-success, #flash-area .alert-info").forEach(function (el) {
      if (window.bootstrap) { bootstrap.Alert.getOrCreateInstance(el).close(); }
    });
  }, 6000);
})();
