<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	import { getBackendConfig } from '$lib/apis';
	import {
		ldapUserSignIn,
		userSignIn,
		userSignUp,
		updateUserTimezone
	} from '$lib/apis/auths';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';
	import { generateInitialsImage, getUserTimezone } from '$lib/utils';

	const i18n = getContext('i18n');

	export let show = false;

	let mode: 'signin' | 'signup' | 'ldap' = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';
	let ldapUsername = '';

	let submitting = false;

	const setSessionUser = async (sessionUser: any) => {
		if (sessionUser) {
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			try {
				await config.set(await getBackendConfig());
			} catch (e) {
				console.error(e);
			}

			const timezone = getUserTimezone();
			if (sessionUser.token && timezone) {
				updateUserTimezone(sessionUser.token, timezone);
			}

			show = false;
		}
	};

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		if ($config?.features?.enable_signup_password_confirmation) {
			if (password !== confirmPassword) {
				toast.error($i18n.t('Passwords do not match.'));
				return;
			}
		}

		const sessionUser = await userSignUp(
			name,
			email,
			password,
			generateInitialsImage(name)
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (submitting) {
			return;
		}

		submitting = true;
		try {
			if (mode === 'ldap') {
				await ldapSignInHandler();
			} else if (mode === 'signin') {
				await signInHandler();
			} else {
				await signUpHandler();
			}
		} finally {
			submitting = false;
		}
	};
</script>

<Modal bind:show size="sm">
	<div class="p-6 text-gray-900 dark:text-gray-100 flex flex-col relative">
		<!-- Close Button -->
		<button
			type="button"
			class="absolute top-4 right-4 p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
			on:click={() => {
				show = false;
			}}
			aria-label={$i18n.t('Close')}
		>
			<XMark className="size-5" />
		</button>

		<!-- Header with Logo and Title -->
		<div class="flex flex-col items-center text-center mt-2 mb-4">
			<img
				crossorigin="anonymous"
				src="{WEBUI_BASE_URL}/static/favicon.png"
				class="size-14 rounded-full shadow-md mb-3"
				alt="{$WEBUI_NAME} logo"
			/>
			<div class="text-xl font-semibold text-gray-900 dark:text-white">
				{#if mode === 'ldap'}
					{$i18n.t(`Sign in to {{WEBUI_NAME}} with LDAP`, { WEBUI_NAME: $WEBUI_NAME })}
				{:else if mode === 'signin'}
					{$i18n.t(`Sign in to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
				{:else}
					{$i18n.t(`Sign up to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
				{/if}
			</div>

			<!-- Traffic / Registration Guidance Banner -->
			<div class="mt-3 w-full text-xs py-2 px-3 rounded-xl bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200/80 dark:border-blue-900/60 flex items-center justify-between gap-2 shadow-xs">
				<div class="flex items-center gap-1.5 min-w-0 text-left">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-4 shrink-0 text-blue-600 dark:text-blue-400">
						<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clip-rule="evenodd" />
					</svg>
					<span class="truncate">还没账号？请前往 <strong>ztoken.cc</strong> 注册账号</span>
				</div>
				<a
					href="https://ztoken.cc/sign-in"
					target="_blank"
					rel="noopener noreferrer"
					class="shrink-0 px-2.5 py-1 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition flex items-center gap-1 shadow-xs"
				>
					<span>去注册</span>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="size-3">
						<path fill-rule="evenodd" d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z" clip-rule="evenodd" />
					</svg>
				</a>
			</div>
		</div>

		<!-- Form -->
		<form
			class="flex flex-col space-y-3.5 mt-2"
			on:submit={(e) => {
				e.preventDefault();
				submitHandler();
			}}
		>
			{#if mode === 'signup'}
				<div>
					<label for="modal-name" class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 block">
						{$i18n.t('Name')}
					</label>
					<input
						bind:value={name}
						type="text"
						id="modal-name"
						class="w-full text-sm rounded-xl px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 outline-none focus:border-blue-500 transition placeholder:text-gray-400 dark:placeholder:text-gray-500"
						autocomplete="name"
						placeholder={$i18n.t('Enter Your Full Name')}
						required
					/>
				</div>
			{/if}

			{#if mode === 'ldap'}
				<div>
					<label for="modal-ldap-username" class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 block">
						{$i18n.t('Username')}
					</label>
					<input
						bind:value={ldapUsername}
						type="text"
						id="modal-ldap-username"
						class="w-full text-sm rounded-xl px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 outline-none focus:border-blue-500 transition placeholder:text-gray-400 dark:placeholder:text-gray-500"
						autocomplete="username"
						placeholder={$i18n.t('Enter Your Username')}
						required
					/>
				</div>
			{:else}
				<div>
					<label for="modal-email" class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 block">
						{mode === 'signin' ? `${$i18n.t('Username')} / ${$i18n.t('Email')}` : $i18n.t('Email')}
					</label>
					<input
						bind:value={email}
						type={mode === 'signin' ? 'text' : 'email'}
						id="modal-email"
						class="w-full text-sm rounded-xl px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 outline-none focus:border-blue-500 transition placeholder:text-gray-400 dark:placeholder:text-gray-500"
						autocomplete="username"
						placeholder={mode === 'signin'
							? `${$i18n.t('Enter Your Username')} / ${$i18n.t('Email')}`
							: $i18n.t('Enter Your Email')}
						required
					/>
				</div>
			{/if}

			<div>
				<label for="modal-password" class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 block">
					{$i18n.t('Password')}
				</label>
				<div class="rounded-xl px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 focus-within:border-blue-500 transition">
					<SensitiveInput
						bind:value={password}
						type="password"
						id="modal-password"
						class="text-sm outline-none"
						placeholder={$i18n.t('Enter Your Password')}
						autocomplete={mode === 'signup' ? 'new-password' : 'current-password'}
						name="password"
						required
					/>
				</div>
			</div>

			{#if mode === 'signup' && $config?.features?.enable_signup_password_confirmation}
				<div>
					<label for="modal-confirm-password" class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 block">
						{$i18n.t('Confirm Password')}
					</label>
					<div class="rounded-xl px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 focus-within:border-blue-500 transition">
						<SensitiveInput
							bind:value={confirmPassword}
							type="password"
							id="modal-confirm-password"
							class="text-sm outline-none"
							placeholder={$i18n.t('Confirm Your Password')}
							autocomplete="new-password"
							name="confirm-password"
							required
						/>
					</div>
				</div>
			{/if}

			<button
				class="bg-blue-600 hover:bg-blue-700 text-white transition w-full rounded-xl font-medium text-sm py-2.5 disabled:opacity-50 flex items-center justify-center mt-2 shadow-sm"
				type="submit"
				disabled={submitting}
			>
				<span>
					{mode === 'ldap'
						? $i18n.t('Authenticate')
						: mode === 'signin'
						? $i18n.t('Sign in')
						: $i18n.t('Create Account')}
				</span>
				{#if submitting}
					<span class="ml-2">
						<Spinner className="size-4" />
					</span>
				{/if}
			</button>
		</form>

		<!-- Traffic / Registration Guidance Link -->
		<div class="mt-4 text-xs text-center text-gray-500 dark:text-gray-400">
			{$i18n.t("Don't have an account?")}
			<a
				href="https://ztoken.cc/sign-in"
				target="_blank"
				rel="noopener noreferrer"
				class="font-medium text-blue-600 dark:text-blue-400 hover:underline ml-1 inline-flex items-center gap-0.5"
			>
				<span>前往 ztoken.cc 注册账号</span>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="size-3">
					<path fill-rule="evenodd" d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z" clip-rule="evenodd" />
				</svg>
			</a>
		</div>

		<!-- OAuth Options -->
		{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
			<div class="inline-flex items-center justify-center w-full my-3">
				<hr class="w-full h-px border-0 bg-gray-200 dark:bg-gray-700" />
				<span class="px-2 text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-900 absolute">
					{$i18n.t('or')}
				</span>
			</div>

			<div class="flex flex-col space-y-2">
				{#if $config?.oauth?.providers?.google}
					<button
						type="button"
						class="flex justify-center items-center bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-750 border border-gray-200 dark:border-gray-700 transition w-full rounded-xl font-normal text-xs py-2 text-gray-700 dark:text-gray-200"
						on:click={() => {
							window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="size-4 mr-2" aria-hidden="true">
							<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
							<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
							<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
							<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
						</svg>
						<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
					</button>
				{/if}
				{#if $config?.oauth?.providers?.github}
					<button
						type="button"
						class="flex justify-center items-center bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-750 border border-gray-200 dark:border-gray-700 transition w-full rounded-xl font-normal text-xs py-2 text-gray-700 dark:text-gray-200"
						on:click={() => {
							window.location.href = `${WEBUI_BASE_URL}/oauth/github/login`;
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 mr-2" aria-hidden="true">
							<path fill="currentColor" d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z" />
						</svg>
						<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitHub' })}</span>
					</button>
				{/if}
			</div>
		{/if}
	</div>
</Modal>
