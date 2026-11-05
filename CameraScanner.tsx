import React, { useRef, useState } from "react";
import {
  View,
  Text,
  Button,
  Image,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
  Switch,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Location from "expo-location";

const API_URL = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "");

interface PlantCandidate {
  scientific_name: string;
  score: number;
  is_multiflora_rose: boolean;
}

interface PromptA {
  title: string;
  message: string;
  tool: string;
  recommendations: string[];
  safety_note: string;
}

interface PlantResult {
  success: boolean;
  species: string;
  confidence: number;
  multiflora_rose_candidate: boolean;
  candidates: PlantCandidate[];
  prompt_a?: PromptA;
  prompt_b?: {
    available: boolean;
    message: string;
    note: string;
  };
}

interface ConsentResponse {
  consent_id: string;
  expires_at: string;
}

interface SightingResponse {
  stored: boolean;
  map_display_enabled: boolean;
  environmental_sharing_authorized: boolean;
  environmental_notification_status: string;
  message: string;
}

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail || body.message || "Request failed.";
  } catch {
    return "Request failed. Please try again.";
  }
}

export default function CameraScanner() {
  const camera = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [photo, setPhoto] = useState<string | null>(null);
  const [result, setResult] = useState<PlantResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Prompt B choices default to OFF. No location permission is requested on scan.
  const [mapOptIn, setMapOptIn] = useState(false);
  const [environmentalOptIn, setEnvironmentalOptIn] = useState(false);
  const [speciesConfirmed, setSpeciesConfirmed] = useState(false);
  const [consentId, setConsentId] = useState<string | null>(null);
  const [consentExpiresAt, setConsentExpiresAt] = useState<string | null>(null);
  const [sightingMessage, setSightingMessage] = useState<string | null>(null);

  if (!permission) return <View />;

  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Camera Permission</Text>
        <Button title="Allow Camera" onPress={requestPermission} />
      </View>
    );
  }

  async function captureAndIdentify() {
    if (!camera.current || !cameraReady || loading) return;
    if (!API_URL) {
      setError("Backend URL is not configured. Set EXPO_PUBLIC_API_URL.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSightingMessage(null);
    setConsentId(null);
    setConsentExpiresAt(null);
    setMapOptIn(false);
    setEnvironmentalOptIn(false);
    setSpeciesConfirmed(false);

    try {
      const picture = await camera.current.takePictureAsync({ quality: 0.85 });
      if (!picture) throw new Error("No photograph captured.");
      setPhoto(picture.uri);

      const formData = new FormData();
      formData.append("file", {
        uri: picture.uri,
        name: "plant.jpg",
        type: "image/jpeg",
      } as any);

      const response = await fetch(`${API_URL}/scan`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error(await responseError(response));

      const data: PlantResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to identify plant.");
    } finally {
      setLoading(false);
    }
  }

  async function submitVoluntarySighting() {
    if (!API_URL || loading || !result?.multiflora_rose_candidate) return;
    if (!speciesConfirmed) {
      setError("Please confirm that you reviewed the Multiflora Rose identification before submitting.");
      return;
    }
    if (!mapOptIn && !environmentalOptIn) {
      setError("Choose at least one optional use, or leave Prompt B without submitting.");
      return;
    }

    setLoading(true);
    setError(null);
    setSightingMessage(null);

    try {
      // This OS permission prompt only runs after the user presses Submit Sighting.
      // Declining permission exits without creating consent or transmitting coordinates.
      const permissionResult = await Location.requestForegroundPermissionsAsync();
      if (!permissionResult.granted) {
        throw new Error("Location permission was not granted. No consent or sighting was submitted.");
      }

      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      const consentResponse = await fetch(`${API_URL}/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          map_display_opt_in: mapOptIn,
          environmental_sharing_opt_in: environmentalOptIn,
          device_location_permission_confirmed: true,
          duration_days: 7,
        }),
      });
      if (!consentResponse.ok) throw new Error(await responseError(consentResponse));

      const consent: ConsentResponse = await consentResponse.json();
      setConsentId(consent.consent_id);
      setConsentExpiresAt(consent.expires_at);

      const sightingResponse = await fetch(`${API_URL}/sightings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          consent_id: consent.consent_id,
          species: "Rosa multiflora",
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      });
      if (!sightingResponse.ok) throw new Error(await responseError(sightingResponse));

      const sighting: SightingResponse = await sightingResponse.json();
      setSightingMessage(
        sighting.message +
          (sighting.environmental_notification_status === "not_configured"
            ? " Environmental-group notifications are not connected yet; no message was sent."
            : "")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit sighting.");
    } finally {
      setLoading(false);
    }
  }

  async function revokeConsent() {
    if (!API_URL || !consentId || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/consent/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent_id: consentId }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      setConsentId(null);
      setConsentExpiresAt(null);
      setSightingMessage("Consent revoked and associated stored sighting deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revoke consent.");
    } finally {
      setLoading(false);
    }
  }

  function resetScanner() {
    setPhoto(null);
    setResult(null);
    setError(null);
    setCameraReady(false);
    setMapOptIn(false);
    setEnvironmentalOptIn(false);
    setSpeciesConfirmed(false);
    setConsentId(null);
    setConsentExpiresAt(null);
    setSightingMessage(null);
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        <Text style={styles.title}>Allied Algorithms</Text>
        <Text style={styles.subtitle}>AI Plant Identifier</Text>

        {!photo && (
          <CameraView
            ref={camera}
            style={styles.camera}
            facing="back"
            onCameraReady={() => setCameraReady(true)}
          />
        )}

        {photo && <Image source={{ uri: photo }} style={styles.camera} />}

        {!photo && (
          <Button
            title="Capture and Identify"
            onPress={captureAndIdentify}
            disabled={!cameraReady || loading}
          />
        )}

        {loading && (
          <View style={styles.loading}>
            <ActivityIndicator size="large" color="#267A43" />
            <Text>Working...</Text>
          </View>
        )}

        {error && (
          <View style={styles.result}>
            <Text style={styles.error}>{error}</Text>
          </View>
        )}

        {result && (
          <View style={styles.result}>
            <Text style={styles.heading}>Identification Result</Text>
            <Text style={styles.species}>{result.species}</Text>
            <Text>Confidence: {(result.confidence * 100).toFixed(1)}%</Text>
            <Text>
              Multiflora Rose candidate: {result.multiflora_rose_candidate ? "Yes" : "No"}
            </Text>
            <Text style={styles.note}>
              AI identification is preliminary and may require expert verification.
            </Text>

            <Text style={styles.heading}>Other possible matches</Text>
            {result.candidates.slice(0, 3).map((candidate, index) => (
              <Text key={index}>
                {candidate.scientific_name} — {(candidate.score * 100).toFixed(1)}%
              </Text>
            ))}
          </View>
        )}

        {result?.multiflora_rose_candidate && (
          <>
            <View style={styles.result}>
              <Text style={styles.heading}>Prompt A — Removal guidance</Text>
              <Text style={styles.species}>{result.prompt_a?.title || "Possible Multiflora Rose detected"}</Text>
              <Text>{result.prompt_a?.message}</Text>
              <Text style={styles.tool}>{result.prompt_a?.tool || "Allied Algorithms specialized net-cutter"}</Text>
              {(result.prompt_a?.recommendations || []).map((item, index) => (
                <Text key={index} style={styles.bullet}>• {item}</Text>
              ))}
              <Text style={styles.note}>{result.prompt_a?.safety_note}</Text>
            </View>

            {!consentId ? (
              <View style={styles.result}>
                <Text style={styles.heading}>Prompt B — Optional location submission</Text>
                <Text>{result.prompt_b?.message}</Text>
                <Text style={styles.note}>
                  Both choices start OFF. You can decline by doing nothing. Scanning does not request location.
                </Text>

                <View style={styles.switchRow}>
                  <View style={styles.switchText}>
                    <Text style={styles.optionTitle}>Show my sighting on my map</Text>
                    <Text style={styles.note}>Allows this sighting to appear in your consent-scoped map data.</Text>
                  </View>
                  <Switch value={mapOptIn} onValueChange={setMapOptIn} />
                </View>

                <View style={styles.switchRow}>
                  <View style={styles.switchText}>
                    <Text style={styles.optionTitle}>Authorize environmental-group sharing</Text>
                    <Text style={styles.note}>
                      Separate optional permission. Group notification delivery is not connected yet; nothing is sent to a group at this time.
                    </Text>
                  </View>
                  <Switch value={environmentalOptIn} onValueChange={setEnvironmentalOptIn} />
                </View>

                <View style={styles.switchRow}>
                  <View style={styles.switchText}>
                    <Text style={styles.optionTitle}>I reviewed and confirm this is Multiflora Rose</Text>
                    <Text style={styles.note}>Please verify the plant before submitting a location.</Text>
                  </View>
                  <Switch value={speciesConfirmed} onValueChange={setSpeciesConfirmed} />
                </View>

                <Text style={styles.note}>
                  If you choose to submit, the app will then ask for your device's foreground location permission. If you deny it, no consent or sighting is submitted. Consent expires after 7 days and can be revoked.
                </Text>
                <Button
                  title="Submit Sighting (Optional)"
                  onPress={submitVoluntarySighting}
                  disabled={loading || (!mapOptIn && !environmentalOptIn) || !speciesConfirmed}
                />
                <Button title="No Thanks — Do Not Share" onPress={() => setSightingMessage("No location was requested or submitted.")} />
              </View>
            ) : (
              <View style={styles.result}>
                <Text style={styles.heading}>Sighting consent active</Text>
                <Text style={styles.note}>Consent expires: {consentExpiresAt ? new Date(consentExpiresAt).toLocaleString() : "in 7 days"}</Text>
                <Button title="Revoke Consent and Delete Sighting" color="#B42318" onPress={revokeConsent} disabled={loading} />
              </View>
            )}
          </>
        )}

        {sightingMessage && (
          <View style={styles.result}>
            <Text>{sightingMessage}</Text>
          </View>
        )}

        {result && (
          <Button title="Scan Another Plant" onPress={resetScanner} disabled={loading} />
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F3F7F1" },
  content: { padding: 20, paddingTop: 60, paddingBottom: 40, gap: 12 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { fontSize: 28, fontWeight: "bold", color: "#245B36" },
  subtitle: { fontSize: 17, marginBottom: 8, color: "#667366" },
  camera: { width: "100%", height: 400, borderRadius: 16 },
  loading: { alignItems: "center", margin: 25, gap: 12 },
  result: { padding: 18, marginTop: 8, backgroundColor: "#FFFFFF", borderRadius: 14, gap: 12 },
  heading: { fontSize: 19, fontWeight: "bold", color: "#245B36" },
  species: { fontSize: 22, fontWeight: "bold", color: "#267A43" },
  note: { fontSize: 12, color: "#667366" },
  error: { color: "#B42318" },
  tool: { fontWeight: "bold", color: "#245B36" },
  bullet: { lineHeight: 21 },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  switchText: { flex: 1, gap: 4 },
  optionTitle: { fontWeight: "600", color: "#243524" },
});
