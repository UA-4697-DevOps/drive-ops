package main

import (
	"log"
	"net/http"
	"os"
)

func main() {
	// Get port by env, else use 8080
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// Мinimal healthcheck
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("TripService is running"))
	})

	log.Printf("Server starting on port %s...", port)
	
	// Server start
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}