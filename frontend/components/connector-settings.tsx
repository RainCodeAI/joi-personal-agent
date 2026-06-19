"use client";

import { useState } from "react";

import { disconnectConnector, startGoogleOauth } from "@/lib/api";
import type { Connector } from "@/lib/types";


export function ConnectorSettings({ connectors: initial }: { connectors: Connector[] }) {
  const [connectors, setConnectors] = useState(initial);
  const [status, setStatus] = useState("Ready");

  async function disconnect(connector: Connector) {
    if (!window.confirm(`Disconnect ${connector.label}? Joi will lose access until you reconnect.`)) {
      return;
    }
    setStatus(`Disconnecting ${connector.label}`);
    try {
      const response = await disconnectConnector(connector.id);
      setConnectors((current) =>
        current.map((item) => item.id === response.connector.id ? response.connector : item),
      );
      setStatus(`${connector.label} disconnected`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Disconnect failed");
    }
  }

  async function connectGoogle() {
    setStatus("Starting Google authorization");
    try {
      const response = await startGoogleOauth();
      window.location.assign(response.auth_url);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Authorization failed");
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Connected Apps</p>
      <h3>Connector access</h3>
      <div className="list">
        {connectors.map((connector) => (
          <div className="list-row" key={connector.id}>
            <div>
              <strong>{connector.label}</strong>
              <p>{connector.capabilities.join(", ")}</p>
            </div>
            <div className="button-row">
              <span className={`badge ${connector.connected ? "ok" : ""}`}>
                {connector.connected ? "connected" : "not connected"}
              </span>
              {connector.connected ? (
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => void disconnect(connector)}
                >
                  Disconnect
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      <div className="button-row" style={{ marginTop: 12 }}>
        <button className="button ghost" type="button" onClick={() => void connectGoogle()}>
          Connect Google
        </button>
        <span className="badge">{status}</span>
      </div>
    </section>
  );
}
