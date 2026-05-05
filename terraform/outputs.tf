output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Public IPv4 address of the instance"
  value       = aws_instance.app.public_ip
}

output "public_dns" {
  description = "Public DNS hostname of the instance"
  value       = aws_instance.app.public_dns
}

output "ssh_command" {
  description = "Ready-to-use SSH command"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.app.public_ip}"
}

output "app_url" {
  description = "URL to open the SRE Shop frontend"
  value       = "http://${aws_instance.app.public_ip}"
}

output "grafana_url" {
  description = "URL of the Grafana dashboard"
  value       = "http://${aws_instance.app.public_ip}:3000"
}

output "prometheus_url" {
  description = "URL of the Prometheus UI"
  value       = "http://${aws_instance.app.public_ip}:9090"
}

output "alertmanager_url" {
  description = "URL of the Alertmanager UI (Assignment 6 §4.2.3)"
  value       = "http://${aws_instance.app.public_ip}:9093"
}

output "instance_size" {
  description = "EC2 instance type currently provisioned (vertical-scaling knob)"
  value       = var.instance_type
}

output "service_replicas" {
  description = "Number of order-service replicas (horizontal-scaling knob)"
  value       = var.service_replicas
}
