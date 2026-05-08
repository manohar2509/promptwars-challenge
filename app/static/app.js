/**
 * Travel Planning Engine - Client-side JavaScript
 * Handles form submission as JSON via fetch (bypasses HTMX form encoding issues)
 */
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('preferences-form');
  if (!form) return;

  form.addEventListener('submit', async (evt) => {
    evt.preventDefault();

    const errorDiv = document.getElementById('form-error');
    const overlay = document.getElementById('loading-overlay');
    const submitBtn = form.querySelector('button[type="submit"]');

    // Show loading state
    if (overlay) overlay.style.display = 'flex';
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData(form);
    const interests = formData.getAll('interests');
    const dietaryRestrictions = formData.getAll('dietary_restrictions');

    const payload = {
      destination: formData.get('destination'),
      start_date: formData.get('start_date'),
      end_date: formData.get('end_date'),
      budget_amount: parseFloat(formData.get('budget_amount')) || 0,
      budget_currency: formData.get('budget_currency') || 'USD',
      interests: interests,
      travel_style: formData.get('travel_style'),
      group_size: parseInt(formData.get('group_size')) || 1,
      accessibility: {
        wheelchair_accessible: formData.get('wheelchair_accessible') === 'on',
        elevator_required: formData.get('elevator_required') === 'on',
        dietary_restrictions: dietaryRestrictions,
        mobility_notes: formData.get('mobility_notes') || ''
      }
    };

    try {
      const resp = await fetch('/api/plan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'HX-Request': 'true',
        },
        body: JSON.stringify(payload),
      });

      if (resp.status === 204 || resp.ok) {
        // Check for HX-Redirect header
        const redirect = resp.headers.get('HX-Redirect');
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

      // Error response
      const text = await resp.text();
      let html;
      try {
        const data = JSON.parse(text);
        const messages = Array.isArray(data.detail)
          ? data.detail.map(e => e.msg || e.message || JSON.stringify(e))
          : [data.detail || 'An error occurred'];
        html = `<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700" role="alert">
          <p class="font-semibold">Please fix the following:</p>
          <ul class="list-disc pl-5 mt-2">${messages.map(m => `<li>${m}</li>`).join('')}</ul>
        </div>`;
      } catch {
        html = `<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700" role="alert">${text || 'An unexpected error occurred. Please try again.'}</div>`;
      }
      if (errorDiv) errorDiv.innerHTML = html;
    } catch (err) {
      if (errorDiv) {
        errorDiv.innerHTML = `<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700" role="alert">Network error: ${err.message}. Please try again.</div>`;
      }
    } finally {
      if (overlay) overlay.style.display = 'none';
      if (submitBtn) submitBtn.disabled = false;
    }
  });
});

/**
 * Initialize Google Map on itinerary page
 */
function initMap(slots, center) {
  if (!window.google || !document.getElementById('map')) return;

  const map = new google.maps.Map(document.getElementById('map'), {
    zoom: 13,
    center: center,
    mapTypeControl: false,
  });

  const bounds = new google.maps.LatLngBounds();
  const path = [];

  slots.forEach((slot, index) => {
    if (slot.lat && slot.lng) {
      const position = { lat: slot.lat, lng: slot.lng };
      const marker = new google.maps.Marker({
        position,
        map,
        label: String(index + 1),
        title: slot.name,
      });
      bounds.extend(position);
      path.push(position);
    }
  });

  if (path.length > 1) {
    new google.maps.Polyline({
      path,
      geodesic: true,
      strokeColor: '#3B82F6',
      strokeOpacity: 0.8,
      strokeWeight: 3,
      map,
    });
  }

  if (path.length > 0) {
    map.fitBounds(bounds);
  }
}
