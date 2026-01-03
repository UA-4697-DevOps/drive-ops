**Docker part**

- Local run: 
 ```bash
  docker-compose up -d --build
  ```

- Deploy Vagrant VM:
 ```bash
  ansible-playbook -i inventory deploy.yml
  ```

- Diagnostics and Troubleshooting(This section will help you troubleshoot problems if events are not passing through the system.)
 ```bash
  docker-compose ps
  ```

- View Logs(If the service is not working correctly, check the console output)
 ```bash
  docker-сompose logs -f driver-service
  ```
