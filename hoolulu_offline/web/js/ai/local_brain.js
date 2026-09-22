// The offline brain: routes your prompt to a local skill, scaffolds projects, or
// falls back to a structured answer. Deterministic and instant — no network,
// no weights, no API key. This is the floor the app never drops below.

import * as db from '../db.js';
import { SKILLS } from './skills.js';
import { generate, detectStack, extractTopic, listStacks } from './scaffold.js';
import { uid, money } from '../util.js';

export const BRAIN = {
  id: 'local',
  label: 'Offline brain',
  model: 'local-brain',
};

const BUILD_RE = /\b(build|scaffold|generate|spin up|set up|make|write|start|create)\b[\s\S]{0,70}?\b(app|application|site|website|web app|webapp|landing page|landing|dashboard|admin panel|analytics|api|backend|server|endpoint|bot|telegram bot|discord bot|extension|chrome extension|browser extension|script|cli|tool|page|calculator|form|portfolio|prototype|store|shop|crm)\b/i;
const SCAFFOLD_RE = /\b(build|scaffold|generate|spin up)\b/i;

function scoreSkill(skill, lower, prompt) {
  let score = 0;
  for (const k of skill.keywords || []) {
    if (lower.includes(k)) score += k.split(' ').length >= 2 ? 3 : 2;
  }
  for (const re of skill.patterns || []) {
    if (re.test(prompt)) score += 5;
  }
  return score;
}

/** Decide which local skill (if any) should answer this prompt. */
export function route(prompt) {
  const lower = String(prompt || '').toLowerCase();
  const scored = SKILLS
    .map(s => ({ skill: s, score: scoreSkill(s, lower, prompt) }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score);
  return scored.length ? scored[0] : null;
}

export function wantsScaffold(prompt) {
  const p = String(prompt || '');
  if (BUILD_RE.test(p)) return 'strong';
  if (/\bscaffold\b/i.test(p)) return 'strong';
  if (SCAFFOLD_RE.test(p) && !route(p)) return 'weak';
  return null;
}

// ------------------------------------------------------------------ scaffold

async function scaffoldProject(prompt, { settings, explicitStack = null }) {
  const stackId = explicitStack || detectStack(prompt).id;
  const built = generate(stackId, { prompt });
  const name = built.name;

  const project = await db.put('projects', {
    name,
    stack: built.stack,
    status: 'building',
    description: `Scaffolded offline: ${prompt}`.slice(0, 240),
    entry: built.entry,
    created_at: Date.now(),
  });

  for (const f of built.files) {
    await db.put('files', {
      project_id: project.id,
      path: f.path,
      content: f.content,
      created_at: Date.now(),
    });
  }

  // Three starter tasks so the project opens with momentum, not a blank page.
  const starters = [
    `Open ${built.entry} and make the first edit`,
    'Replace the placeholder copy with your real content',
    'Add one feature that only you would think of',
  ];
  for (const t of starters) {
    await db.put('tasks', { project_id: project.id, title: t, status: 'todo', created_at: Date.now() });
  }

  const tree = built.files
    .map(f => `\`${f.path}\` — ${f.content.split('\n').length} lines`)
    .join('\n');

  return {
    text: `## Built: ${name}

**Stack:** ${built.label} · **${built.files.length} files** · saved to **Projects**

${tree}

**Run it**
${built.notes.map(n => `- ${n}`).join('\n')}

Everything is editable in the built-in editor (Projects → open it → click a
file), and the **Preview** button renders static projects right here, offline.

Want it different? Say *"rebuild ${name} as a Flask API"* or *"add a login page to ${name}"*.`,
    created: [{ type: 'project', id: project.id, label: `${name} (${built.files.length} files)` }],
    followups: [`Add a feature to ${name}`, `Plan ${name}`, `Price ${name}`],
    projectId: project.id,
  };
}

// ------------------------------------------------------------------- fallback

function fallback(prompt, { settings }) {
  const p = String(prompt || '').trim();
  const topic = p.replace(/[.?!]+$/, '');
  const isQuestion = /\?$/.test(p) || /^(what|why|how|when|who|is|are|can|should|do|does)\b/i.test(p);

  return {
    text: `## Offline brain

I'm running locally with no model loaded, so I can't reason freely about
"${topic.slice(0, 80)}" — but I can still work the problem with you.

${isQuestion
      ? `**How I'd get you an answer offline**

1. **Narrow it.** What exactly do you need to decide or produce? One sentence.
2. **Name the shape of the answer.** A plan, a piece of writing, a number, or code? Different skills.
3. **Hand it to a skill that does exist offline** — see the list below.
4. **Or queue it.** Anything you send while offline gets answered by the real model the moment you reconnect or load an on-device one.`
      : `**How I'd approach it**

1. **Write down what "done" looks like** — one sentence, checkable.
2. **Find the smallest version** that is real. Fake data is fine; missing flow is not.
3. **Do that**, then show one person.
4. **Ship, then invoice the same day.**`}

**Skills that work right now, offline**

| Say this | You get |
| --- | --- |
| \`money\` | revenue, pipeline, outstanding, profit |
| \`proposal for <client>\` | a drafted, saved proposal |
| \`invoice <client> for $800\` | a numbered invoice |
| \`price 30 hours\` | floor / target / premium pricing |
| \`plan a <thing>\` | a phased plan (say *"create it as a project"* to save it) |
| \`build a <thing>\` | runnable files, scaffolded locally |
| \`standup\` | what moved today |
| \`cold email to <client>\` | three outreach variants |
| \`regex\` · \`sql\` · \`cron\` · \`git\` · \`css\` | battle-tested snippets |
| \`debug <problem>\` | a structured path through it |
| \`checklist\` | launch / client-onboarding checklists |

**Stacks I can scaffold:** ${listStacks().map(s => s.label).join(', ')}.

> To get real reasoning offline, open **Settings → On-device model** and download
> one (about 1GB, once). After that it runs with the wifi off, forever.`,
    confidence: 0.25,
    followups: ['Show me my money report', 'Build a landing page', 'What can you do offline?'],
  };
}

// ----------------------------------------------------------------------- run

/**
 * @param {object} args
 * @param {string} args.prompt
 * @param {object} args.settings
 * @param {object} args.runtime   { online, serverOk, pending, lastSyncAt, engine, webllmModel }
 * @param {object} args.context   { projectId, conversationId }
 */
export async function run({ prompt, settings = {}, runtime = {}, context = {} }) {
  const started = performance.now();

  // 1. Explicit scaffold request wins outright.
  const mode = wantsScaffold(prompt);
  const hasSkill = route(prompt);
  if (mode === 'strong' || (mode === 'weak' && !hasSkill)) {
    const out = await scaffoldProject(prompt, { settings });
    return { ...out, provider: BRAIN.id, model: BRAIN.model, skill: 'scaffold',
      confidence: 0.9, ms: Math.round(performance.now() - started) };
  }

  // 2. Otherwise the best-scoring local skill.
  const match = hasSkill;
  if (match && match.score >= 2) {
    const out = await match.skill.run({ prompt, settings, runtime, context, lower: String(prompt).toLowerCase() });
    return {
      text: out.text,
      created: out.created || [],
      followups: out.followups || [],
      provider: BRAIN.id,
      model: BRAIN.model,
      skill: match.skill.id,
      title: match.skill.title,
      confidence: Math.min(0.95, 0.55 + match.score * 0.06),
      ms: Math.round(performance.now() - started),
    };
  }

  // 3. Structured fallback.
  const out = fallback(prompt, { settings });
  return { ...out, provider: BRAIN.id, model: BRAIN.model, skill: 'fallback',
    created: [], ms: Math.round(performance.now() - started) };
}

export const LOCAL_SKILLS = SKILLS.map(s => ({ id: s.id, title: s.title, keywords: s.keywords.slice(0, 6) }));
