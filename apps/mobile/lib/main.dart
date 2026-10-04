import 'package:flutter/material.dart';

void main() => runApp(const QueueManagerApp());

class QueueManagerApp extends StatelessWidget {
  const QueueManagerApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Queue Manager',
    theme: ThemeData(useMaterial3: true),
    home: const HomeScreen(),
  );
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Queue Manager')),
    body: const Center(child: Text('Customer / Admin app scaffold')),
  );
}
