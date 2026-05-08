/**
 * Travel Planning Engine — Client-side JavaScript
 *
 * Handles:
 * - Form submission as JSON via fetch (bypasses HTMX form encoding issues)
 * - Google Maps initialisation on itinerary pages
 * - Accessible form validation announcements
 *
 * @module app
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("preferences-form");
  if (!form) return;

  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();

    const errorDiv = document.getElementById("form-error");
    const overlay = document.getElementById("loading-overlay");
    const submitBtn = form.querySelector('button[type="submit"]');

    // Clear previous errors and announce loading state
    if (errorDiv) {
      errorDiv.innerHTML = "";
      errorDiv.removeAttribute("role");
    }

    // Show loading state
    if (overlay) overlay.style.display = "flex";
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData(form);
    const interests = formData.getAll("interests");
    const dietaryRestrictions = formData.getAll("dietary_restrictions");

    // Client-side validation
    if (interests.length === 0) {
      _showError(errorDiv, "Please select at least one interest.");
      if (overlay) overlay.style.display = "none";
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    const payload = {
      destination: formData.get("destination"),
      start_date: formData.get("start_date"),
      end_date: formData.get("end_date"),
      budget_amount: parseFloat(formData.get("budget_amount")) || 0,
      budget_currency: formData.get("budget_currency") || "USD",
      interests: interests,
      travel_style: formData.get("travel_style"),
      group_size: parseInt(formData.get("group_size"), 10) || 1,
      accessibility: {
        wheelchair_accessible: formData.get("wheelchair_accessible") === "on",
        elevator_required: formData.get("elevator_required") === "on",
        dietary_restrictions: dietaryRestrictions,
        mobility_notes: formData.get("mobility_notes") || "",
      },
    };

    try {
      const resp = await fetch("/api/plan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "HX-Request": "true",
        },
        body: JSON.stringify(payload),
      });

      if (resp.status === 204 || resp.ok) {
        // Check for HX-Redirect header
        const redirect = resp.headers.get("HX-Redirect");
        if (redirect) {
          window.location.href = redirect;
          return;
        }
        // Fallback: parse JSON response for plan id
        const data = await resp.json();
        if (data.id) {
          window.location.href = `/plan/${data.id}`;
          return;
        }
      }

      // Error response — parse and display
      _handleErrorResponse(resp, errorDiv);
    } catch (_err) {
      _showError(
        errorDiv,
        "Unable to connect. Please check your internet connection and try again."
      );
    } finally {
      if (overlay) overlay.style.display = "none";
      if (submitBtn) submitBtn.disabled = false;
    }
  });
});

/**
 * Show an error message in the error div with proper ARIA attributes.
 * @param {HTMLElement|null} errorDiv - The error display container.
 * @param {string} message - The error message to display.
 */
function _showError(errorDiv, message) {
  if (!errorDiv) return;
  errorDiv.setAttribute("role", "alert");
  errorDiv.setAttribute("aria-live", "assertive");
  errorDiv.innerHTML =
    '<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">' +
    message +
    "</div>";
}

/**
 * Parse an error HTTP response and display messages.
 * @param {Response} resp - The fetch Response object.
 * @param {HTMLElement|null} errorDiv - The error display container.
 */
async function _handleErrorResponse(resp, errorDiv) {
  try {
    const text = await resp.text();
    try {
      const data = JSON.parse(text);
      const messages = Array.isArray(data.detail)
        ? data.detail.map((e) => e.msg || e.message || JSON.stringify(e))
        : [data.detail || "Something went wrong. Please try again."];
      const html =
        '<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700" role="alert">' +
        '<p class="font-semibold">Please fix the following:</p>' +
        '<ul class="list-disc pl-5 mt-2">' +
        messages.map((m) => "<li>" + m + "</li>").join("") +
        "</ul></div>";
      if (errorDiv) {
        errorDiv.setAttribute("role", "alert");
        errorDiv.setAttribute("aria-live", "assertive");
        errorDiv.innerHTML = html;
      }
    } catch (_jsonErr) {
      _showError(
        errorDiv,
        "Something went wrong. Please check your inputs and try again."
      );
    }
  } catch (_networkErr) {
    _showError(errorDiv, "Something went wrong. Please try again.");
  }
}

/**
 * Initialise Google Maps on the itinerary page.
 * Displays markers for each activity slot and connects them with a polyline.
 *
 * @param {Array<{lat: number, lng: number, name: string}>} slots - Marker data.
 * @param {{lat: number, lng: number}} center - Initial map centre.
 */
function initMap(slots, center) {
  const mapDiv = document.getElementById("map");
  if (!window.google || !mapDiv) return;

  // Clear loading text
  mapDiv.innerHTML = "";

  const map = new google.maps.Map(mapDiv, {
    zoom: 13,
    center: { lat: center.lat, lng: center.lng },
    mapTypeControl: false,
  });

  const bounds = new google.maps.LatLngBounds();
  const path = [];

  slots.forEach((slot, index) => {
    if (slot.lat && slot.lng) {
      const position = { lat: slot.lat, lng: slot.lng };
      new google.maps.Marker({
        position: position,
        map: map,
        label: String(index + 1),
        title: slot.name || "",
      });
      bounds.extend(position);
      path.push(position);
    }
  });

  if (path.length > 1) {
    new google.maps.Polyline({
      path: path,
      geodesic: true,
      strokeColor: "#3B82F6",
      strokeOpacity: 0.8,
      strokeWeight: 3,
      map: map,
    });
    map.fitBounds(bounds);
  } else if (path.length === 1) {
    map.setCenter(path[0]);
    map.setZoom(14);
  }
}
