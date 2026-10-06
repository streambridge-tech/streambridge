export function renderHome() {
  return `<div class="cfg-empty">
    <svg class="cfg-empty-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M2.2 4.2h4l1.1 1.3h6.5c.4 0 .7.3.7.7v6.3c0 .4-.3.7-.7.7H2.2c-.4 0-.7-.3-.7-.7V4.9c0-.4.3-.7.7-.7z"/></svg>
    <div class="cfg-empty-title">Select a folder</div>
    <div class="cfg-empty-desc">Create a parent folder with +, then use ··· to add a file or folder inside.</div>
    <div class="cfg-empty-actions">
      <button class="cfg-btn cfg-btn-primary" type="button" data-new-folder="">New folder</button>
    </div>
  </div>`;
}
