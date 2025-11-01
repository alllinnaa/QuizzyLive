-- Сесія живої вікторини
create table if not exists public.game_sessions (
id uuid primary key default gen_random_uuid(),
quiz_id uuid not null references public.quizzes(id) on delete cascade,
room_code text not null unique,
created_at timestamptz not null default now(),
ended_at timestamptz
);


-- Учасники сесії
create table if not exists public.game_participants (
id uuid primary key default gen_random_uuid(),
session_id uuid not null references public.game_sessions(id) on delete cascade,
name text not null,
joined_at timestamptz not null default now()
);
create index if not exists idx_participants_session on public.game_participants(session_id);


-- Відповіді у межах сесії
create table if not exists public.game_answers (
id uuid primary key default gen_random_uuid(),
session_id uuid not null references public.game_sessions(id) on delete cascade,
participant_id uuid not null references public.game_participants(id) on delete cascade,
question_id uuid not null references public.questions(id) on delete cascade,
question_index int not null,
option_index smallint not null check (option_index between 0 and 3),
is_correct boolean not null,
answered_at timestamptz not null default now()
);
create index if not exists idx_answers_session_question on public.game_answers(session_id, question_index);
create index if not exists idx_answers_participant on public.game_answers(participant_id);


-- Підсумкова таблиця очок (опційно; можна обчислювати на льоту)
create table if not exists public.game_scores (
session_id uuid not null references public.game_sessions(id) on delete cascade,
participant_id uuid not null references public.game_participants(id) on delete cascade,
score int not null default 0,
primary key (session_id, participant_id)
);