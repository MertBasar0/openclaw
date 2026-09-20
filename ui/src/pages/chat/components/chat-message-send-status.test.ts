import { render } from "lit";
import { describe, expect, it, vi } from "vitest";
import { renderChatSendStatus } from "./chat-message-send-status.ts";

describe("renderChatSendStatus", () => {
  it.each([
    { state: "failed", actionLabel: undefined, retry: true, discard: true },
    { state: "failed", actionLabel: "Check failure", retry: true, discard: false },
    { state: "unconfirmed", actionLabel: undefined, retry: true, discard: true },
    { state: "unconfirmed", actionLabel: "Check delivery", retry: true, discard: false },
    { state: "waiting-reconnect", actionLabel: undefined, retry: false, discard: true },
  ] as const)(
    "shows a $state footer with its diagnostic and recovery actions ($actionLabel)",
    ({ state, actionLabel, retry: canRetry, discard: canDiscard }) => {
      const container = document.createElement("div");
      const onRetryQueuedMessage = vi.fn();
      const onDiscardQueuedMessage = vi.fn();
      render(
        renderChatSendStatus(
          { id: "attempted-send", state, error: "Delivery diagnostic" },
          {
            onRetryQueuedMessage,
            onDiscardQueuedMessage,
            queuedMessageAction: actionLabel
              ? { id: "attempted-send", label: actionLabel }
              : undefined,
          },
        ),
        container,
      );

      const status = container.querySelector<HTMLElement>(".chat-send-status");
      expect(status).not.toBeNull();
      expect(status?.title).toBe("Delivery diagnostic");
      const retry = status?.querySelector<HTMLButtonElement>(".chat-send-status__retry");
      expect(Boolean(retry)).toBe(canRetry);
      retry?.click();
      expect(onRetryQueuedMessage.mock.calls).toEqual(canRetry ? [["attempted-send"]] : []);
      const discard = status?.querySelector<HTMLButtonElement>(".chat-send-status__discard");
      if (canDiscard) {
        discard?.click();
        expect(onDiscardQueuedMessage).toHaveBeenCalledWith("attempted-send");
        discard?.dispatchEvent(new MouseEvent("click", { bubbles: true, detail: 2 }));
        expect(onDiscardQueuedMessage).toHaveBeenCalledTimes(1);
        expect(onRetryQueuedMessage).toHaveBeenCalledTimes(canRetry ? 1 : 0);
      } else {
        expect(discard).toBeNull();
      }
    },
  );

  it("returns nothing when status is null", () => {
    const container = document.createElement("div");
    render(renderChatSendStatus(null, {}), container);
    expect(container.querySelector(".chat-send-status")).toBeNull();
  });
});
