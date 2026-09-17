# Support Copilot · Service Workspace

## Direction
A focused enterprise support workspace for agents reviewing evidence and resolving customer issues, team leads triaging risk, and administrators governing knowledge. Existing React/Ant Design primitives are retained and refined. Reference: the embedded redesign audit and Linear's precise density, type hierarchy and restrained borders, adapted to a light service workspace with evergreen identity. No brand assets or invented operational results.

## Color and material
CSS variables in `src/index.css` are the source for UI tokens. Canvas #f5f7f6; white surface #ffffff; muted surface #f0f4f2; navigation #152b26; primary text #233b33; secondary #576b61; muted #53665b; line #dfe7e2; soft line #edf1ee. Accent #16775f; hover #105e4a; accent soft #e8f4ee. Semantic red, amber, green retain readable text plus labels. Borders separate panes; shallow shadow only for dialogs and floating tools. No illustrative hero inside the workspace.

## Typography
System UI sans with PingFang SC / Microsoft YaHei for Chinese; SFMono-Regular for identifiers. Scale: 11 metadata, 12 caption, 13 controls, 14 body, 16 panel heading, 20 ticket title, 24 page heading, 28 metrics. Weights 400/500/600/700. Body line-height 1.6, customer messages 1.85. All metric numbers tabular. Long identifiers wrap or truncate without widening layout.

## Layout and spacing
4px base; 4/8/12/16/20/24/32 rhythm. Navigation 208px, toolbar 76px, workbench summary 88px. Desktop >=1440: queue 304px, flexible context, assistant 360px. Compact desktop >=1100: queue 272px, flexible context, assistant 320px, rail 176px. Tablet: queue 280px with context and assistant stacked. Mobile <720: horizontal navigation and explicit queue/detail navigation; detail and assistant stack. No essential actions disappear at small sizes. Independent pane scrolling on wide desktop; natural document flow on compact screens.

## Primitives
Existing Ant Button/Input/Select/Modal/Tabs are the reusable interactive layer. All form controls have labels and inline validation. Shell navigation uses icon + label + current-page state. Queue rows carry identity, subject, customer and priority/status, with selected border and accent wash. Section headers: title + supporting context + optional action. EmptyState provides cause + recovery. StatusStrip displays actual API metrics or explicit absence. Lifecycle actions are derived from the server's existing transition rules. Internal note editor is separate from reviewed customer reply. AI recommendations always identify evidence and review state.

## Interaction
140ms color/border feedback; 180ms opacity/transform entrance. No artificial streaming or fabricated step progress. Respect prefers-reduced-motion. Commands disable during requests; errors stay visible and retain input. Modal traps focus and restores it; Escape dismisses unless a write is pending. Search updates actual queue data, with stale-request cancellation. Refresh does not erase selected context. Command search uses Cmd/Ctrl+K and provides real navigation/results.

## Accessibility
Semantic landmarks, skip link, aria-current, selected rows with aria-pressed, labeled search/select/textarea. Minimum 36px controls, 44px mobile targets. Visible 2px focus ring. Status is never encoded only in color. Charts retain readable table equivalents. 375/768/1280/1600 viewport verification and axe checks are required.

## Verification and remaining debt
Use existing build budget, Vitest, Java tests, and Playwright plus real API scenarios. This is an existing component system redesign; image concepts and marketing-screen research are not necessary for the operational surface. No external fonts, tracking or dev-instrumentation dependency required by the product. Auth uses the existing configured modes; SSO login and multi-tenant isolation need separate production work. Actual audit results and screenshots are recorded in `docs/enterprise-workspace/VERIFICATION.md`.

The CSS variables are the shared palette for custom workspace surfaces. Ant Design seed tokens in App.tsx and ECharts options in OverviewView.tsx remain explicit component adapters; this iteration does not claim one exhaustive token library for every legacy style. On mobile, operational tables use labeled stacked records so target, actor, trace, gate and latency stay directly visible without discovering horizontal scrolling.
