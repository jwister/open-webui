/**
 * Filter and grouping utilities for models in Open WebUI chat dialog
 */

const CHAT_ENDPOINT_TYPES = new Set([
	'openai',
	'openai-response',
	'openai-response-compact',
	'openai-alpha-search',
	'anthropic',
	'gemini'
]);

const VIDEO_NAME_SUBSTRINGS = [
	'video',
	'sora',
	'kling',
	'vidu',
	'cogvideo',
	'hailuo',
	'dream-machine',
	'pika',
	'animatediff',
	'pixverse',
	'viggle',
	'runway'
];

const VIDEO_NAME_PATTERNS = [
	/(?:^|[-_./])(veo|t2v|i2v|v2v)(?:[-_./]|$|\d)/i,
	/(?:^|[-_./])wan(?:2(?:\.1)?)?(?:[-_./]|$)/i,
	/(?:^|[-_./])luma(?:[-_./]|$)/i,
	/(?:^|[-_./])gen-?[23](?:[-_./]|$)/i
];

const NON_CHAT_NAME_SUBSTRINGS = [
	'embedding',
	'rerank',
	'whisper',
	'babbage',
	'davinci',
	'dall-e',
	'midjourney',
	'flux',
	'stable-diffusion',
	'sdxl',
	'imagen',
	'recraft',
	'kolors',
	'cosyvoice',
	'chattts',
	'text-similarity',
	'text-search'
];

const NON_CHAT_NAME_PATTERNS = [
	/(?:^|[-_./])tts(?:[-_./]|$|\d)/i
];

/**
 * Returns true if the model is a text conversational model.
 * Explicitly filters out video generation, image generation, embedding, rerank, and audio/TTS models.
 */
export function isTextChatModel(model: any): boolean {
	if (!model) return false;

	const modelId = String(model.id || model.value || '').trim().toLowerCase();
	const modelName = String(model.name || model.label || '').trim().toLowerCase();
	const text = `${modelId} ${modelName}`;

	if (!text.trim()) return false;

	// Check supported endpoint types
	const rawEndpoints =
		model.supported_endpoint_types ||
		model.model?.supported_endpoint_types ||
		model.model?.openai?.supported_endpoint_types ||
		model.openai?.supported_endpoint_types;

	if (Array.isArray(rawEndpoints) && rawEndpoints.length > 0) {
		const endpoints = rawEndpoints.map((ep: any) => String(ep).trim().toLowerCase());
		if (
			endpoints.includes('openai-video') ||
			endpoints.some((ep: string) => ep.includes('video') || ep.includes('embedding') || ep.includes('rerank'))
		) {
			return false;
		}
	}

	// Check video substrings
	for (const sub of VIDEO_NAME_SUBSTRINGS) {
		if (text.includes(sub)) return false;
	}

	// Check video regex patterns
	for (const pat of VIDEO_NAME_PATTERNS) {
		if (pat.test(text)) return false;
	}

	// Check non-chat substrings
	for (const sub of NON_CHAT_NAME_SUBSTRINGS) {
		if (text.includes(sub)) return false;
	}

	// Check non-chat regex patterns
	for (const pat of NON_CHAT_NAME_PATTERNS) {
		if (pat.test(text)) return false;
	}

	// 严格过滤：必须属于已知主流对话模型品牌，过滤掉“其他模型”
	if (getModelGroup(model).id === 'other') {
		return false;
	}

	return true;
}

export interface ModelGroupInfo {
	id: string;
	name: string;
	order: number;
}

const KNOWN_GROUPS: ModelGroupInfo[] = [
	{ id: 'openai', name: 'OpenAI', order: 10 },
	{ id: 'claude', name: 'Claude', order: 20 },
	{ id: 'deepseek', name: 'DeepSeek', order: 30 },
	{ id: 'gemini', name: 'Gemini', order: 40 },
	{ id: 'qwen', name: 'Qwen (通义千问)', order: 50 },
	{ id: 'glm', name: 'GLM (智谱)', order: 60 },
	{ id: 'doubao', name: 'Doubao (豆包)', order: 70 },
	{ id: 'kimi', name: 'Kimi (月之暗面)', order: 80 },
	{ id: 'grok', name: 'Grok (xAI)', order: 90 },
	{ id: 'minimax', name: 'MiniMax', order: 100 },
	{ id: 'llama', name: 'Llama (Meta)', order: 110 },
	{ id: 'mistral', name: 'Mistral', order: 120 },
	{ id: 'hunyuan', name: '腾讯混元', order: 130 },
	{ id: 'sensenova', name: '商汤日日新', order: 140 },
	{ id: 'yi', name: 'Yi (零一万物)', order: 150 },
	{ id: 'ernie', name: '文心一言', order: 160 },
	{ id: 'spark', name: '讯飞星火', order: 170 },
	{ id: 'step', name: '阶跃星辰', order: 180 },
	{ id: 'baichuan', name: '百川智能', order: 190 },
	{ id: 'phi', name: 'Phi (微软)', order: 200 },
	{ id: 'cohere', name: 'Command (Cohere)', order: 210 },
	{ id: 'perplexity', name: 'Perplexity', order: 220 },
	{ id: 'other', name: '其他模型', order: 999 }
];

const GROUP_MAP = new Map<string, ModelGroupInfo>(KNOWN_GROUPS.map((g) => [g.id, g]));

function getGroup(id: string): ModelGroupInfo {
	return GROUP_MAP.get(id) || GROUP_MAP.get('other') || { id: 'other', name: '其他模型', order: 999 };
}

/**
 * Determine which brand/family group a model belongs to.
 */
export function getModelGroup(modelOrItem: any): ModelGroupInfo {
	const model = modelOrItem?.model || modelOrItem;
	const modelId = String(modelOrItem?.value || model?.id || '').trim().toLowerCase();
	const modelName = String(modelOrItem?.label || model?.name || '').trim().toLowerCase();
	const combined = `${modelId} ${modelName}`;

	// 1. OpenAI (GPT, o1, o3, o4, chatgpt)
	if (/(?:^|[-_./])(gpt|o1|o3|o4|chatgpt)(?:[-_./]|$)/i.test(combined) || combined.includes('openai')) {
		return getGroup('openai');
	}

	// 2. Claude / Anthropic
	if (combined.includes('claude') || combined.includes('anthropic')) {
		return getGroup('claude');
	}

	// 3. DeepSeek
	if (combined.includes('deepseek')) {
		return getGroup('deepseek');
	}

	// 4. Gemini / Google
	if (
		combined.includes('gemini') ||
		combined.includes('gemma') ||
		combined.includes('learnlm') ||
		combined.includes('google')
	) {
		return getGroup('gemini');
	}

	// 5. Qwen / 通义千问
	if (
		combined.includes('qwen') ||
		combined.includes('qwq') ||
		combined.includes('qvq') ||
		combined.includes('tongyi') ||
		combined.includes('aliyun') ||
		combined.includes('alibaba')
	) {
		return getGroup('qwen');
	}

	// 6. GLM / 智谱
	if (combined.includes('glm') || combined.includes('chatglm') || combined.includes('zhipu')) {
		return getGroup('glm');
	}

	// 7. Doubao / 豆包
	if (
		combined.includes('doubao') ||
		combined.includes('skylark') ||
		combined.includes('volcengine') ||
		combined.includes('bytedance')
	) {
		return getGroup('doubao');
	}

	// 8. Kimi / Moonshot
	if (combined.includes('moonshot') || combined.includes('kimi')) {
		return getGroup('kimi');
	}

	// 9. Grok / xAI
	if (combined.includes('grok') || combined.includes('xai')) {
		return getGroup('grok');
	}

	// 10. MiniMax
	if (combined.includes('minimax') || combined.includes('abab')) {
		return getGroup('minimax');
	}

	// 11. Llama / Meta
	if (combined.includes('llama') || combined.includes('meta-llama')) {
		return getGroup('llama');
	}

	// 12. Mistral
	if (
		combined.includes('mistral') ||
		combined.includes('mixtral') ||
		combined.includes('codestral') ||
		combined.includes('pixtral')
	) {
		return getGroup('mistral');
	}

	// 13. Hunyuan / 腾讯混元
	if (combined.includes('hunyuan') || combined.includes('tencent')) {
		return getGroup('hunyuan');
	}

	// 14. SenseNova / 商汤日日新
	if (
		combined.includes('sensenova') ||
		combined.includes('sensechat') ||
		combined.includes('shangtang') ||
		combined.includes('sensetime')
	) {
		return getGroup('sensenova');
	}

	// 15. Yi / 零一万物
	if (combined.includes('yi-') || combined.includes('01-ai')) {
		return getGroup('yi');
	}

	// 16. ERNIE / 文心一言
	if (combined.includes('ernie') || combined.includes('wenxin') || combined.includes('baidu')) {
		return getGroup('ernie');
	}

	// 17. Spark / 讯飞星火
	if (combined.includes('spark') || combined.includes('xfyun') || combined.includes('iflytek')) {
		return getGroup('spark');
	}

	// 18. Step / 阶跃星辰
	if (combined.includes('step-') || combined.includes('stepfun')) {
		return getGroup('step');
	}

	// 19. Baichuan / 百川
	if (combined.includes('baichuan')) {
		return getGroup('baichuan');
	}

	// 20. Phi / 微软
	if (/(?:^|[-_./])phi(?:[-_./]|$|\d)/i.test(combined) || combined.includes('microsoft')) {
		return getGroup('phi');
	}

	// 21. Cohere / Command
	if (combined.includes('command-r') || combined.includes('cohere')) {
		return getGroup('cohere');
	}

	// 22. Perplexity
	if (combined.includes('sonar') || combined.includes('perplexity')) {
		return getGroup('perplexity');
	}

	// Fallback to owned_by
	const ownedBy = String(model?.owned_by || model?.openai?.owned_by || '').trim().toLowerCase();
	if (ownedBy && ownedBy !== 'openai' && ownedBy !== 'unknown') {
		if (ownedBy.includes('anthropic')) return getGroup('claude');
		if (ownedBy.includes('google')) return getGroup('gemini');
		if (ownedBy.includes('deepseek')) return getGroup('deepseek');
		if (ownedBy.includes('meta')) return getGroup('llama');
		if (ownedBy.includes('alibaba') || ownedBy.includes('qwen')) return getGroup('qwen');
		if (ownedBy.includes('zhipu') || ownedBy.includes('glm')) return getGroup('glm');
		if (ownedBy.includes('bytedance') || ownedBy.includes('doubao')) return getGroup('doubao');
		if (ownedBy.includes('moonshot') || ownedBy.includes('kimi')) return getGroup('kimi');
		if (ownedBy.includes('minimax')) return getGroup('minimax');
		if (ownedBy.includes('mistral')) return getGroup('mistral');
		if (ownedBy.includes('tencent') || ownedBy.includes('hunyuan')) return getGroup('hunyuan');
		if (ownedBy.includes('baidu')) return getGroup('ernie');
		if (ownedBy.includes('sensetime') || ownedBy.includes('shangtang')) return getGroup('sensenova');
		if (ownedBy.includes('stepfun')) return getGroup('step');
		if (ownedBy.includes('baichuan')) return getGroup('baichuan');
		if (ownedBy.includes('microsoft')) return getGroup('phi');
		if (ownedBy.includes('cohere')) return getGroup('cohere');
		if (ownedBy.includes('perplexity')) return getGroup('perplexity');
	}

	return getGroup('other');
}
