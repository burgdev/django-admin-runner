# django-admin-runner

<div class="md-hero" data-md-color="primary">
  <div class="md-hero__inner">
    <h1>django-admin-runner</h1>
    <p class="md-hero__tagline">
      Run Django management commands from the admin with auto-generated forms,
      pluggable task runners, and a unified execution log.
    </p>
    <div class="md-hero__buttons">
      <a href="quickstart/" class="md-button">Get Started</a>
      <a href="examples/" class="md-button md-button--secondary">See Examples</a>
    </div>
  </div>
</div>

<div class="feature-grid">

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div>
<h3><code>@register_command</code></h3>
<p>Register any management command with a decorator. Add group labels, permissions, and model attachments.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg></div>
<h3>Auto-generated forms</h3>
<p>argparse arguments become Django form fields automatically. No manual form writing needed.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/><circle cx="12" cy="12" r="3"/></svg></div>
<h3>Widget customisation</h3>
<p>Override widgets per-argument, supply a custom <code>Form</code> class, or use decorator-level overrides.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
<h3>Built-in file fields</h3>
<p><code>FileOrPathField</code> (upload or server path), <code>FileField</code>, and <code>ImageField</code> out of the box.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="6" height="6" rx="1"/><rect x="16" y="2" width="6" height="6" rx="1"/><rect x="9" y="13" width="6" height="6" rx="1"/><path d="M5 8v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M12 11v2"/></svg></div>
<h3>Pluggable runners</h3>
<p>Django Tasks (default), Celery, sync, or write your own for any queue backend.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg></div>
<h3>Execution log</h3>
<p>Every run stored as a <code>CommandExecution</code> with full audit trail and rich HTML results.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg></div>
<h3>Permission control</h3>
<p>Per-command: superuser-only, Django permission strings, or AND-combined lists.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></div>
<h3>Model attachment</h3>
<p>Show a "Run" button on any model's admin change-list via <code>models=[...]</code>.</p>
</div>

<div class="feature-card">
<div class="feature-icon"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2 12h3v8h6v-6h2v6h6v-8h3Z"/></svg></div>
<h3>Unfold support</h3>
<p>Auto-detected. Uses Unfold templates and widgets when installed.</p>
</div>

</div>

## Quick navigation

- [Installation](installation.md) — get set up in under a minute
- [Quickstart](quickstart.md) — register and run your first command
- [Decorator reference](../guides/decorator.md) — all `@register_command` options
- [Runners](../guides/runners.md) — built-in and custom runners
- [Execution context](../guides/execution-context.md) — rich output and ANSI support
- [Hooks](../guides/hooks.md) — run code before and after command execution
- [Admin themes](../guides/admin-themes.md) — plain Django admin and Unfold
- [Examples](../examples.md) — complete example projects
