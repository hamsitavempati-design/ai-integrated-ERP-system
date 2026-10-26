import { useState, useRef, useEffect } from "react";
import "./App.css";
import "bootstrap/dist/css/bootstrap.min.css";
import robotAvatar from "./assets/erp-robot.png";

function App() {
  const [messages, setMessages] = useState([
    {
      text: "Hi! 👋 I’m your ERP Assistant. How can I help you today?",
      sender: "bot",
    },
  ]);

  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [isOpen, setIsOpen] = useState(false);

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // ---------------------------------------------------------
  // BUILD CHAT HISTORY
  // ---------------------------------------------------------
  const getChatHistory = () => {
    return messages
      .filter((msg) => msg.text && msg.text.trim())
      .map((msg) => ({
        role: msg.sender === "user" ? "user" : "assistant",
        content: msg.text,
      }));
  };

  // ---------------------------------------------------------
  // SEND MESSAGE
  // ---------------------------------------------------------
  const sendMessage = () => {
    if (!input.trim() && !attachment) return;

    const currentInput = input;
    const currentAttachment = attachment;

    const userMessage = {
      text: currentAttachment
        ? `${currentInput} (${currentAttachment.name})`
        : currentInput,
      sender: "user",
    };

    // Capture history BEFORE adding the new message.
    // Then add the current user question separately.
    const historyForRequest = [
      ...getChatHistory(),
      {
        role: "user",
        content: userMessage.text,
      },
    ];

    setMessages((prev) => [...prev, userMessage]);

    setInput("");
    setAttachment(null);

    generateReply(
      currentInput,
      currentAttachment,
      historyForRequest
    );
  };

  // ---------------------------------------------------------
  // GENERATE AI REPLY
  // ---------------------------------------------------------
  const generateReply = async (
    userText,
    selectedFile = null,
    history = []
  ) => {
    setTyping(true);

    try {
      window.parent.postMessage(
        {
          type: "chat-loading",
          loading: true,
          text: "Assistant is typing…",
        },
        "*"
      );
    } catch (e) {}

    try {
      let response;

      // -----------------------------------------------------
      // UPLOAD CSV / EXCEL
      // -----------------------------------------------------
      if (
        selectedFile &&
        !selectedFile.type.startsWith("image/")
      ) {
        const uploadData = new FormData();

        uploadData.append("file", selectedFile);

        const uploadResponse = await fetch(
          "http://localhost:8000/upload",
          {
            method: "POST",
            body: uploadData,
          }
        );

        const uploadResult = await uploadResponse.json();

        if (!uploadResponse.ok) {
          throw new Error(
            uploadResult.message || "Upload failed"
          );
        }
      }

      // -----------------------------------------------------
      // IMAGE ATTACHMENT
      // -----------------------------------------------------
      if (
        selectedFile &&
        selectedFile.type.startsWith("image/")
      ) {
        const chatData = new FormData();

        chatData.append(
          "prompt",
          userText ||
            "Describe this image for my ERP analysis."
        );

        chatData.append("file", selectedFile);

        chatData.append(
          "chat_history",
          JSON.stringify(history)
        );

        response = await fetch(
          "http://localhost:8000/chat",
          {
            method: "POST",
            body: chatData,
          }
        );
      }

      // -----------------------------------------------------
      // NORMAL ERP CHAT
      // -----------------------------------------------------
      else {
        response = await fetch(
          "http://localhost:8000/chat",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },

            body: JSON.stringify({
              prompt:
                userText ||
                "Summarize the available ERP data.",

              chat_history: history,
            }),
          }
        );
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.response || "The request failed"
        );
      }

      const botReplyText = String(
        data.response ||
          "The ERP Assistant returned an empty response."
      );

      // -----------------------------------------------------
      // TYPEWRITER EFFECT
      // -----------------------------------------------------
      let index = 0;
      let tempText = "";

      const messageId =
        Date.now() +
        Math.random();

      const interval = setInterval(() => {
        tempText += botReplyText[index];
        index++;

        setMessages((prev) => {
          const updated = [...prev];

          const existingIndex = updated.findIndex(
            (message) => message.id === messageId
          );

          if (existingIndex !== -1) {
            updated[existingIndex] = {
              ...updated[existingIndex],
              text: tempText,
            };
          } else {
            updated.push({
              id: messageId,
              text: tempText,
              sender: "bot",
            });
          }

          try {
            window.parent.postMessage(
              {
                type: "chat-message",
                id: messageId,
                text: tempText,
                partial: true,
              },
              "*"
            );
          } catch (e) {}

          return updated;
        });

        // ---------------------------------------------------
        // FINISHED TYPING
        // ---------------------------------------------------
        if (index >= botReplyText.length) {
          clearInterval(interval);

          setMessages((prev) =>
            prev.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    sender: "bot",
                  }
                : message
            )
          );

          setTyping(false);

          try {
            window.parent.postMessage(
              {
                type: "chat-loading",
                loading: false,
              },
              "*"
            );
          } catch (e) {}

          try {
            window.parent.postMessage(
              {
                type: "chat-message",
                id: messageId,
                text: botReplyText,
                partial: false,
              },
              "*"
            );
          } catch (e) {}
        }
      }, 15);
    } catch (error) {
      console.error("Connection Error:", error);

      setMessages((prev) => [
        ...prev,
        {
          text:
            "I couldn't connect to the ERP Assistant right now. Please try again.",
          sender: "bot",
        },
      ]);

      setTyping(false);

      try {
        window.parent.postMessage(
          {
            type: "chat-loading",
            loading: false,
          },
          "*"
        );
      } catch (e) {}
    }
  };

  // ---------------------------------------------------------
  // OPEN CHAT
  // ---------------------------------------------------------
  const openChat = () => {
    setIsOpen(true);
  };

  // ---------------------------------------------------------
  // CLOSE CHAT
  // ---------------------------------------------------------
  const closeChat = () => {
    setIsOpen(false);
  };

  // ---------------------------------------------------------
  // IFRAME READY
  // ---------------------------------------------------------
  useEffect(() => {
    try {
      window.parent.postMessage(
        {
          type: "chat-ready",
        },
        "*"
      );
    } catch (e) {}
  }, []);

  // ---------------------------------------------------------
  // RECEIVE MESSAGE FROM PARENT ERP DASHBOARD
  // ---------------------------------------------------------
  useEffect(() => {
    function onMessage(event) {
      if (
        !event.data ||
        typeof event.data !== "object"
      ) {
        return;
      }

      // -----------------------------------------------------
      // HOST FORWARDED USER MESSAGE
      // -----------------------------------------------------
      if (
        event.data.type === "send-message" &&
        event.data.text
      ) {
        const text = String(event.data.text);

        setIsOpen(true);

        setMessages((prev) => {
          const history = [
            ...prev,
            {
              text,
              sender: "user",
            },
          ];

          // Generate reply using the exact history
          // that includes the forwarded message.
          setTimeout(() => {
            const formattedHistory = history
              .filter(
                (message) =>
                  message.text &&
                  message.text.trim()
              )
              .map((message) => ({
                role:
                  message.sender === "user"
                    ? "user"
                    : "assistant",
                content: message.text,
              }));

            generateReply(
              text,
              null,
              formattedHistory
            );
          }, 60);

          return history;
        });
      }

      // -----------------------------------------------------
      // PING FROM HOST
      // -----------------------------------------------------
      if (event.data.type === "ping") {
        try {
          window.parent.postMessage(
            {
              type: "pong",
            },
            "*"
          );
        } catch (e) {}
      }
    }

    window.addEventListener(
      "message",
      onMessage
    );

    return () => {
      window.removeEventListener(
        "message",
        onMessage
      );
    };
  }, []);

  // ---------------------------------------------------------
  // AUTO SCROLL
  // ---------------------------------------------------------
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  // ---------------------------------------------------------
  // RENDER
  // ---------------------------------------------------------
  return (
    <div className="app-container">

      {/* =====================================================
          CLOSED STATE
          ROBOT + HELP MESSAGE ONLY
      ===================================================== */}
      {!isOpen && (
        <div className="assistant-launcher">

          <div className="help-bubble">
            <div className="help-title">
              Need help?
            </div>

            <div className="help-text">
              Ask me anything!
            </div>
          </div>

          <button
            className="robot-avatar-button"
            onClick={openChat}
            aria-label="Open ERP Assistant"
            title="Open ERP Assistant"
          >
            <img
              src={robotAvatar}
              alt="ERP Assistant"
              className="robot-avatar"
            />
          </button>

        </div>
      )}

      {/* =====================================================
          OPEN CHAT WINDOW
      ===================================================== */}
      {isOpen && (
        <div className="chat-widget">

          {/* HEADER */}
          <div className="chat-header">

            <div className="header-avatar">
              <img
                src={robotAvatar}
                alt="ERP Assistant"
              />
            </div>

            <div className="header-info">
              <div className="assistant-name">
                ERP Assistant
              </div>

              <div className="assistant-status">
                <span className="status-dot"></span>
                Online
              </div>
            </div>

            <button
              className="chat-close"
              onClick={closeChat}
              aria-label="Close chatbot"
              title="Close"
            >
              ×
            </button>

          </div>

          {/* CHAT BODY */}
          <div className="chat-body">

            <div className="welcome-area">
              <div className="welcome-avatar">
                <img
                  src={robotAvatar}
                  alt="ERP Assistant"
                />
              </div>

              <div className="welcome-title">
                Your ERP Assistant
              </div>

              <div className="welcome-subtitle">
                Ask about sales, inventory,
                suppliers, forecasts or anything
                related to your business data.
              </div>
            </div>

            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className={`message ${
                  msg.sender === "user"
                    ? "user"
                    : "bot"
                }`}
              >
                {msg.text}
              </div>
            ))}

            {typing && (
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            )}

            <div ref={chatEndRef}></div>

          </div>

          {/* INPUT */}
          <div className="chat-input">

            <button
              className="attach-button"
              type="button"
              aria-label="Attach a CSV, spreadsheet, or image"
              title="Attach a CSV, spreadsheet, or image"
              onClick={() =>
                fileInputRef.current?.click()
              }
            >
              +
            </button>

            <input
              ref={fileInputRef}
              className="file-picker"
              type="file"
              accept=".csv,.xlsx,.xls,image/*"
              onChange={(event) =>
                setAttachment(
                  event.target.files?.[0] || null
                )
              }
            />

            <input
              type="text"
              placeholder={
                attachment
                  ? `Ask about ${attachment.name}...`
                  : "Ask anything about your business..."
              }
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter"
                ) {
                  sendMessage();
                }
              }}
            />

            <button
              className="send-button"
              onClick={sendMessage}
              aria-label="Send message"
              title="Send message"
            >
              ➤
            </button>

          </div>

        </div>
      )}

    </div>
  );
}

export default App;