/* {{NAME}} — small interactions only: accordion, year stamp, tap-to-copy. */
(function () {
  "use strict";

  document.querySelectorAll(".faq details").forEach(function (item) {
    item.addEventListener("toggle", function () {
      if (!item.open) return;
      document.querySelectorAll(".faq details").forEach(function (other) {
        if (other !== item) other.open = false;
      });
    });
  });

  var stamp = document.querySelector("[data-year]");
  if (stamp) stamp.textContent = new Date().getFullYear();

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = button.getAttribute("data-copy");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value);
        var original = button.textContent;
        button.textContent = "Copied";
        setTimeout(function () { button.textContent = original; }, 1500);
      }
    });
  });
})();
