const defaultOllamaBaseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";

export function createAnalysisModel() {
  const provider = (process.env.AI_PROVIDER || "ollama").toLowerCase();

  if (provider === "openai-compatible") {
    return {
      provider,
      modelName: process.env.OPENAI_MODEL || "local-model",
      healthcheck: async () => {
        const ok = Boolean(process.env.OPENAI_BASE_URL);
        return ok ? "OpenAI-compatible endpoint configured." : "Missing OPENAI_BASE_URL.";
      },
      generate: generateViaOpenAICompatible
    };
  }

  return {
    provider: "ollama",
    modelName: process.env.OLLAMA_MODEL || "qwen2.5-coder:32b",
    healthcheck: async () => {
      try {
        const response = await fetch(`${defaultOllamaBaseUrl}/api/tags`);
        if (!response.ok) {
          return `Ollama responded with ${response.status} ${response.statusText}`;
        }
        return "Ollama is reachable.";
      } catch (error) {
        return `Ollama is not reachable: ${error.message}`;
      }
    },
    generate: generateViaOllama
  };
}

async function generateViaOllama({ messages, model }) {
  const response = await fetch(`${defaultOllamaBaseUrl}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      messages,
      stream: false
    })
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();
  return payload?.message?.content ?? "";
}

async function generateViaOpenAICompatible({ messages, model }) {
  const baseUrl = process.env.OPENAI_BASE_URL;
  const apiKey = process.env.OPENAI_API_KEY || "";

  if (!baseUrl) {
    throw new Error("OPENAI_BASE_URL is required for AI_PROVIDER=openai-compatible");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {})
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.2
    })
  });

  if (!response.ok) {
    throw new Error(`OpenAI-compatible request failed: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();
  return payload?.choices?.[0]?.message?.content ?? "";
}

