
import React, { useRef, useState } from "react";

import {
  View,
  Text,
  Button,
  Image,
  ActivityIndicator,
  StyleSheet,
  ScrollView
} from "react-native";

import {
  CameraView,
  useCameraPermissions
} from "expo-camera";

const API_URL = process.env.EXPO_PUBLIC_API_URL;

interface PlantResult {
  success: boolean;
  species: string;
  confidence: number;
  multiflora_rose_candidate: boolean;
  candidates: {
    scientific_name: string;
    score: number;
    is_multiflora_rose: boolean;
  }[];
}

export default function CameraScanner() {

  const camera = useRef<CameraView>(null);

  const [permission, requestPermission] =
    useCameraPermissions();

  const [cameraReady, setCameraReady] = useState(false);
  const [photo, setPhoto] = useState<string | null>(null);
  const [result, setResult] = useState<PlantResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!permission) return <View />;

  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Camera Permission</Text>
        <Button
          title="Allow Camera"
          onPress={requestPermission}
        />
      </View>
    );
  }

  async function captureAndIdentify() {

    if (!camera.current || !cameraReady || loading) return;

    if (!API_URL) {
      setError("Backend URL is not configured.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {

      const picture = await camera.current.takePictureAsync({
        quality: 0.85
      });

      if (!picture) {
        throw new Error("No photograph captured.");
      }

      setPhoto(picture.uri);

      const formData = new FormData();

      formData.append(
        "file",
        {
          uri: picture.uri,
          name: "plant.jpg",
          type: "image/jpeg"
        } as any
      );

      const response = await fetch(
        `${API_URL.replace(/\/$/, "")}/scan`,
        {
          method: "POST",
          body: formData
        }
      );

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "Identification failed.");
      }

      const data: PlantResult = await response.json();

      setResult(data);

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : "Unable to identify plant."
      );

    } finally {
      setLoading(false);
    }
  }

  function resetScanner() {
    setPhoto(null);
    setResult(null);
    setError(null);
    setCameraReady(false);
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>

        <Text style={styles.title}>
          Allied Algorithms
        </Text>

        <Text style={styles.subtitle}>
          AI Plant Identifier
        </Text>

        {!photo && (
          <CameraView
            ref={camera}
            style={styles.camera}
            facing="back"
            onCameraReady={() => setCameraReady(true)}
          />
        )}

        {photo && (
          <Image
            source={{ uri: photo }}
            style={styles.camera}
          />
        )}

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
            <Text>Analyzing plant photograph...</Text>
          </View>
        )}

        {error && (
          <View style={styles.result}>
            <Text style={styles.error}>{error}</Text>
            <Button title="Try Again" onPress={resetScanner} />
          </View>
        )}

        {result && (
          <View style={styles.result}>

            <Text style={styles.heading}>
              Identification Result
            </Text>

            <Text style={styles.species}>
              {result.species}
            </Text>

            <Text>
              Confidence: {(result.confidence * 100).toFixed(1)}%
            </Text>

            <Text>
              Multiflora Rose candidate:{" "}
              {result.multiflora_rose_candidate ? "Yes" : "No"}
            </Text>

            <Text style={styles.note}>
              AI identification is preliminary and may require
              expert verification.
            </Text>

            <Text style={styles.heading}>
              Other possible matches
            </Text>

            {result.candidates.slice(0, 3).map((candidate, index) => (
              <Text key={index}>
                {candidate.scientific_name} —{" "}
                {(candidate.score * 100).toFixed(1)}%
              </Text>
            ))}

            <Button
              title="Scan Another Plant"
              onPress={resetScanner}
            />

          </View>
        )}

      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F7F1"
  },
  content: {
    padding: 20,
    paddingTop: 60,
    paddingBottom: 40
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center"
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#245B36"
  },
  subtitle: {
    fontSize: 17,
    marginBottom: 20,
    color: "#667366"
  },
  camera: {
    width: "100%",
    height: 400,
    borderRadius: 16
  },
  loading: {
    alignItems: "center",
    margin: 25,
    gap: 12
  },
  result: {
    padding: 18,
    marginTop: 20,
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    gap: 12
  },
  heading: {
    fontSize: 19,
    fontWeight: "bold",
    color: "#245B36"
  },
  species: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#267A43"
  },
  note: {
    fontSize: 12,
    color: "#777777"
  },
  error: {
    color: "#B42318"
  }
});

